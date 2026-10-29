from http.server import BaseHTTPRequestHandler, HTTPServer
import json, re, os, sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "compiler_demo.db")
SCHEMA = {"students": ["id", "name", "marks"], "enrollments": ["student_id", "course"]}
KEYWORDS = {"SELECT","FROM","WHERE","JOIN","ON","GROUP","BY","ORDER","ASC","DESC"}
TOKEN_RE = re.compile(r"'(?:''|[^'])*'|<=|>=|!=|<>|[=<>]|[A-Za-z_][A-Za-z0-9_]*|\d+|[,.;*()]")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, marks INTEGER NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS enrollments (student_id INTEGER NOT NULL, course TEXT NOT NULL)")
        count = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        if count == 0:
            conn.executemany("INSERT INTO students(name, marks) VALUES (?, ?)", [
                ("Aman", 78), ("Rohit", 91), ("Navjot", 85)])
            conn.executemany("INSERT INTO enrollments(student_id, course) VALUES (?, ?)", [
                (1, "DBMS"), (2, "Compilers"), (3, "Compilers")])

def tokenize(sql):
    toks = list(TOKEN_RE.finditer(sql))
    residue = re.sub(r"\s+", "", TOKEN_RE.sub("", sql))
    if residue:
        raise ValueError("Lexer error: unsupported character(s): " + residue.strip())
    out = []
    for match in toks:
        t = match.group()
        if t.startswith("'"): typ = "STRING"
        elif t.isdigit(): typ = "NUMBER"
        elif t in ",.;*()": typ = {",":"COMMA",".":"DOT",";":"SEMICOLON","*":"STAR","(":"LPAREN",")":"RPAREN"}[t]
        elif t in {"=","<",">","<=",">=","!=","<>"}: typ = "OPERATOR"
        elif t.upper() in KEYWORDS: typ = t.upper()
        else: typ = "IDENTIFIER"
        out.append({"type": typ, "lexeme": t})
    return out

def compile_query(sql):
    tokens = tokenize(sql)
    stages = [{"name":"1. Lexer","status":"PASS","detail":f"Converted SQL into {len(tokens)} tokens.","data":tokens}]
    q = sql.strip().rstrip(";").strip()
    pattern = (r"(?is)SELECT\s+(.+?)\s+FROM\s+([A-Za-z_]\w*)"
      r"(?:\s+JOIN\s+([A-Za-z_]\w*)\s+ON\s+([\w.]+)\s*=\s*([\w.]+))?"
      r"(?:\s+WHERE\s+([\w.]+)\s*(>=|<=|!=|<>|=|>|<)\s*('(?:''|[^'])*'|\d+|[A-Za-z_]\w*))?"
      r"(?:\s+GROUP\s+BY\s+([\w.]+))?"
      r"(?:\s+ORDER\s+BY\s+([\w.]+)(?:\s+(ASC|DESC))?)?")
    m = re.fullmatch(pattern, q)
    if not m:
        raise ValueError("Syntax error. Supported: SELECT columns FROM table [JOIN table ON a=b] [WHERE column operator value] [GROUP BY column] [ORDER BY column [ASC|DESC]].")
    coltext, table, jtable, jleft, jright, wcol, wop, wval, gcol, ocol, odir = m.groups()
    cols = [c.strip() for c in coltext.split(",")]
    if not cols or any(not re.fullmatch(r"(?:\w+\.)?\w+|\*", c) for c in cols):
        raise ValueError("Syntax error in SELECT column list.")

    
    if table not in SCHEMA: raise ValueError("Semantic error: Unknown table '"+table+"'.")
    if jtable and jtable not in SCHEMA: raise ValueError("Semantic error: Unknown table '"+jtable+"'.")
    def resolve(ref):
        parts = ref.split(".")
        if len(parts) == 2:
            t,c = parts
            if t not in SCHEMA: raise ValueError("Semantic error: Unknown table '"+t+"'.")
            if c not in SCHEMA[t]: raise ValueError("Semantic error: Unknown column '"+c+"' in '"+t+"'.")
            if t not in [table,jtable]: raise ValueError("Semantic error: table '"+t+"' is not in query.")
            return c
        candidates = [t for t in [table,jtable] if t and parts[0] in SCHEMA[t]]
        if not candidates: raise ValueError("Semantic error: Unknown column '"+parts[0]+"'.")
        if len(candidates) > 1: raise ValueError("Semantic error: Ambiguous column '"+parts[0]+"'; qualify it with a table name.")
        return parts[0]
    for c in cols:
        if c != "*": resolve(c)
    for ref in [jleft,jright,wcol,gcol,ocol]:
        if ref: resolve(ref)
    parsed = {"columns":cols,"from":table,"join":({"table":jtable,"condition":jleft+" = "+jright} if jtable else None),
      "where":({"column":wcol,"operator":wop,"value":wval} if wcol else None),"group_by":gcol,"order_by":ocol,"order_direction":(odir or "ASC").upper()}
    stages.append({"name":"2. Parser","status":"PASS","detail":"Parsed the supported SELECT statement.","data":parsed})
    stages.append({"name":"3. Semantic Analyzer","status":"PASS","detail":"Validated table and column references using the schema catalog.","data":SCHEMA})
    plan = {"op":"SCAN","table":table}
    if jtable: plan = {"op":"JOIN","condition":jleft+" = "+jright,"children":[plan,{"op":"SCAN","table":jtable}]}
    if wcol: plan = {"op":"FILTER","predicate":wcol+" "+wop+" "+wval,"child":plan}
    if gcol: plan = {"op":"GROUP_BY","column":gcol,"child":plan}
    plan = {"op":"PROJECT","columns":cols,"child":plan}
    if ocol: plan = {"op":"ORDER_BY","column":ocol,"direction":(odir or "ASC").upper(),"child":plan}
    stages.append({"name":"4. Query Translator","status":"PASS","detail":"Created a relational-algebra tree.","data":plan})
    stages.append({"name":"5. Optimizer","status":"PASS","detail":"Demonstrates filter-before-projection and requested-column output rules; this is a simplified educational optimizer.","data":{"plan":plan,"rules":["Filter before projection where supported","Return only requested columns","ORDER BY applied by the execution engine"]}})
    # Execute the validated SELECT against the persistent SQLite database.
    
    with db() as conn:
        cur = conn.execute(q)
        columns = [d[0] for d in (cur.description or [])]
        result = [dict(row) for row in cur.fetchall()]
    stages.append({"name":"6. Executor","status":"PASS","detail":f"Executed the query against the SQLite database file compiler_demo.db; {len(result)} row(s) returned.","data":result})
    return {"ok":True,"stages":stages,"columns":columns,"rows":result,"row_count":len(result)}

class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store")
        self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path in ["/","/index.html"]:
            with open(os.path.join(os.path.dirname(__file__),"web","index.html"),"rb") as f: body=f.read()
            self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
        elif self.path == "/api/students":
            with db() as conn:
                students = [dict(r) for r in conn.execute("SELECT id,name,marks FROM students ORDER BY id")]
            self.send_json({"ok":True,"students":students})
        else: self.send_error(404)
    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length","0"))
            if n > 100000: raise ValueError("Request is too large.")
            data = json.loads(self.rfile.read(n).decode("utf-8"))
            if self.path == "/api/compile":
                sql = data.get("sql","").strip()
                if not re.match(r"(?is)^SELECT\b", sql): raise ValueError("Only SELECT queries are allowed in the compiler editor.")
                result = compile_query(sql)
                self.send_json(result)
            elif self.path == "/api/students":
                name = str(data.get("name","")).strip()
                marks = data.get("marks")
                course = str(data.get("course","")).strip() or "General"
                if not name: raise ValueError("Please enter a student name.")
                try: marks = int(marks)
                except (ValueError,TypeError): raise ValueError("Marks must be a whole number from 0 to 100.")
                if not 0 <= marks <= 100: raise ValueError("Marks must be between 0 and 100.")
                with db() as conn:
                    cur = conn.execute("INSERT INTO students(name,marks) VALUES (?,?)",(name,marks))
                    sid = cur.lastrowid
                    conn.execute("INSERT INTO enrollments(student_id,course) VALUES (?,?)",(sid,course))
                self.send_json({"ok":True,"message":f"Added {name} to the SQLite database.","id":sid})
            else: self.send_error(404)
        except Exception as e:
            message = str(e)
            if message.startswith("Lexer error"):
                failed_stage = 0
            elif message.startswith("Syntax error"):
                failed_stage = 1
            elif message.startswith("Semantic error"):
                failed_stage = 2
            else:
                failed_stage = 5
            self.send_json({"ok":False,"error":message,"failed_stage":failed_stage},400)
    def log_message(self,fmt,*args): print("[server]",fmt%args)

if __name__ == "__main__":
    init_db()
    print("Mini SQL Compiler (SQLite edition): http://127.0.0.1:8000")
    print("Database: compiler_demo.db (saved in this project folder)")
    print("Keep this window open. Press Ctrl+C to stop.")
    try: HTTPServer(("127.0.0.1",8000),Handler).serve_forever()
    except OSError as e: print("Could not start server:",e); input("Press Enter to close...")
