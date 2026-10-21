from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from pathlib import Path
from urllib.parse import quote_plus, urlencode
from urllib.request import urlopen, Request
from dotenv import load_dotenv

load_dotenv()
import sqlite3, csv, re, time, os, base64, mimetypes

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
DB = BASE / "database" / "auravis.db"
UPLOADS = BASE / "static" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)
DB.parent.mkdir(parents=True, exist_ok=True)
ALLOWED_IMG = {"png", "jpg", "jpeg", "webp", "gif"}

app = Flask(__name__)
app.secret_key = os.getenv("AURAVIS_SECRET_KEY") or "dev-only-change-this-secret-key"
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      avatar TEXT DEFAULT '',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS activity(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      category TEXT NOT NULL,
      action TEXT NOT NULL,
      content_id TEXT DEFAULT '',
      title TEXT DEFAULT '',
      query TEXT DEFAULT '',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS feedback(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      category TEXT NOT NULL,
      content_id TEXT NOT NULL,
      title TEXT DEFAULT '',
      action TEXT NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(user_id, category, content_id),
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS searches(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      query TEXT NOT NULL,
      category TEXT NOT NULL,
      language TEXT DEFAULT 'en',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS user_goals(
      user_id INTEGER PRIMARY KEY,
      goal TEXT DEFAULT 'learn',
      level TEXT DEFAULT 'beginner',
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    c.commit(); c.close()


init_db()


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    c = db(); u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone(); c.close()
    return u


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def load(category):
    filename = "movies.csv" if category == "movies" else "education.csv"
    path = DATA / filename
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    # Some older AURAVIS movie CSV versions had description/rating/director
    # shifted one column. Repair that legacy layout at load time so the old
    # dataset remains usable without deleting or rewriting the user's data.
    if category == "movies":
        for r in rows:
            director = str(r.get("director", "")).strip()
            rating = str(r.get("rating", "")).strip()
            description = str(r.get("description", "")).strip()
            if director.replace(".", "", 1).isdigit() and rating and not rating.replace(".", "", 1).isdigit():
                r["director"], r["rating"], r["description"] = rating, director, description
    return rows



def education_lesson(item):
    """Build a detailed, topic-aware offline lesson from a local education record.

    The lesson is deterministic and needs no API. Specific concepts are selected
    from the result title/topic; generic subject fallbacks never borrow concepts
    from an unrelated subject.
    """
    title = str(item.get("title", "Learning Resource")).strip()
    topic = str(item.get("topic", "General")).strip()
    level = str(item.get("difficulty", "General")).strip()
    desc = str(item.get("description", "")).strip()
    blob = f"{title} {topic}".lower()

    profiles = [
      (["physics", "mechanics", "electric", "magnetic", "optics", "thermodynamics", "wave", "motion", "force", "energy"], {
        "keys":["Physical quantities and laws", "Core principle", "Mathematical relationship", "Worked problem method", "Real-world applications"],
        "details":[["Core idea", "Physics explains matter, energy, motion and interactions using measurable quantities, models and experimentally tested laws."], ["Problem solving", "Identify the known quantities, choose the relevant physical law, keep units consistent, substitute values and check whether the result is physically reasonable."], ["Representation", "Diagrams, graphs, vectors and equations are used together to describe physical systems."], ["Applications", "Physics principles support engineering, electronics, communication, energy systems, transport, medicine and astronomy."]],
        "formulae":["Use SI units and write the governing relation before substituting numerical values."],
        "example":"For a numerical problem, list the given quantities and unknown, select the matching law, substitute values with units, and verify the final unit.",
        "applications":["Engineering systems", "Energy and electronics", "Measurement and experimentation", "Everyday physical phenomena"],
        "revision":["Learn definitions together with units.", "Understand what each equation means rather than memorizing symbols alone.", "Draw a diagram when forces, rays or motion are involved.", "Practise both conceptual and numerical questions."]}),
      (["chemistry", "atomic", "bonding", "stoichiometry", "acid", "base", "organic", "electrochemistry"], {
        "keys":["Particles and structure", "Chemical properties", "Reactions and equations", "Quantitative relationships", "Laboratory and real-world applications"],
        "details":[["Core idea", "Chemistry studies the composition, structure, properties and transformations of matter."], ["Reactions", "Chemical equations represent reactants changing into products and should obey conservation of atoms and charge."], ["Structure and properties", "Atomic structure and bonding help explain why substances have different physical and chemical properties."], ["Quantitative chemistry", "The mole concept connects microscopic particles with measurable laboratory quantities."]],
        "formulae":["Amount of substance: n = mass / molar mass", "For calculations, balance the chemical equation before using mole ratios."],
        "example":"A chemistry problem can be approached by identifying substances, writing a balanced equation, converting known quantities to moles, applying the mole ratio, and converting to the required unit.",
        "applications":["Materials and manufacturing", "Medicines and biochemistry", "Energy and batteries", "Environmental analysis"],
        "revision":["Balance equations carefully.", "Connect periodic trends with atomic structure.", "Learn reaction conditions along with products.", "Keep units and significant quantities clear in calculations."]}),
      (["english language", "grammar", "sentence", "vocabulary", "essay", "writing", "comprehension"], {
        "keys":["Meaning and rule", "Correct usage", "Examples", "Common errors", "Writing and communication practice"],
        "details":[["Language skill", "English language study develops accurate grammar, vocabulary, reading comprehension and clear written and spoken communication."], ["Usage", "A rule becomes useful when it is applied in meaningful sentences rather than memorized in isolation."], ["Reading", "Comprehension involves identifying the main idea, supporting details, purpose, tone and reasonable inferences from a passage."], ["Writing", "Effective writing uses a clear purpose, logical organization, suitable vocabulary, correct grammar and careful revision."]],
        "formulae":[],
        "example":"After learning a grammar or vocabulary concept, write your own sentence, check its meaning and structure, and then revise any error you notice.",
        "applications":["Academic writing", "Professional communication", "Reading comprehension", "Presentations and everyday communication"],
        "revision":["Learn rules through examples.", "Keep a vocabulary list with meanings and sample sentences.", "Plan before writing longer answers.", "Proofread for grammar, punctuation and clarity."]}),
      (["english literature", "poetry", "literary", "novel", "drama", "character", "theme"], {
        "keys":["Text and context", "Plot or structure", "Character and voice", "Theme and literary devices", "Evidence-based interpretation"],
        "details":[["Reading literature", "Literary study examines how writers use language, structure, character, imagery and other devices to communicate ideas and experiences."], ["Interpretation", "A strong interpretation makes a clear point and supports it with specific evidence from the text."], ["Context", "Historical, social and cultural context can help explain a work, but analysis should remain connected to the text itself."], ["Comparison", "Comparing themes, characters or techniques can reveal how different texts approach similar ideas."]],
        "formulae":[],
        "example":"For a theme question, state the theme, identify a relevant moment or technique in the text, explain its effect, and connect it back to the theme.",
        "applications":["Close reading", "Literary essays", "Comparative analysis", "Poetry and drama appreciation"],
        "revision":["Know key literary terms.", "Support interpretations with textual evidence.", "Separate plot summary from analysis.", "Explain the effect of a literary device, not only its name."]}),
      (["biology", "cell", "genetics", "ecology", "photosynthesis", "respiration"], {
        "keys":["Structure", "Function", "Biological process", "Regulation and interaction", "Applications and examples"],
        "details":[["Core idea", "Biology studies living organisms, their structures, functions, inheritance, evolution and relationships with the environment."], ["Structure and function", "Biological structures are best understood by connecting their form with the function they perform."], ["Processes", "Many biological processes involve ordered stages, inputs, outputs and regulation."], ["Levels of organization", "Biological explanations can connect molecules, cells, tissues, organs, organisms, populations and ecosystems."]],
        "formulae":[],
        "example":"When studying a biological process, identify where it occurs, its inputs, major stages, outputs and why the process is important to the organism.",
        "applications":["Health and medicine", "Agriculture", "Biotechnology", "Ecology and conservation"],
        "revision":["Use labelled diagrams where useful.", "Connect structure with function.", "Learn processes in logical sequence.", "Compare closely related terms to avoid confusion."]}),
      (["calculus", "derivative", "integral"], {
        "keys":["Limits and continuity", "Derivatives and rules of differentiation", "Applications of derivatives", "Indefinite and definite integration", "Applications of integration"],
        "details":[
          ["Limits and continuity", "A limit describes the value a function approaches as its input approaches a point. Limits are used to define continuity and form the foundation of differential calculus."],
          ["Derivatives", "A derivative measures instantaneous rate of change and geometrically represents the slope of the tangent to a curve. Common rules include the power, product, quotient and chain rules."],
          ["Integration", "Integration measures accumulation. An indefinite integral represents a family of antiderivatives, while a definite integral evaluates accumulated change over an interval."],
          ["Applications", "Calculus is used for maxima and minima, optimization, motion and rates of change, areas under curves, accumulated quantities and many engineering models."]],
        "formulae":["Derivative definition: f'(x) = lim[h→0] (f(x+h)-f(x))/h", "Power rule: d(x^n)/dx = n·x^(n-1)", "Fundamental relation: integration reverses differentiation", "Definite integral: ∫ from a to b f(x) dx gives signed accumulated area"],
        "example":"For f(x)=x², the power rule gives f'(x)=2x. At x=3, the derivative is 6, so the tangent slope there is 6.",
        "applications":["Optimization and maxima/minima", "Velocity and acceleration", "Area and accumulated change", "Engineering and physical modelling"],
        "revision":["Know the meaning of a limit before learning derivatives.", "Practise standard derivative and integral formulas.", "For application problems, identify the quantity changing before choosing a formula.", "Check constants of integration for indefinite integrals."]}),
      (["deadlock"], {
        "keys":["Deadlock definition", "Four necessary conditions", "Resource-allocation graph", "Prevention and avoidance", "Detection and recovery"],
        "details":[["What is deadlock?", "Deadlock is a state in which a group of processes cannot continue because each is waiting for a resource held by another process in the group."], ["Necessary conditions", "The four Coffman conditions are mutual exclusion, hold and wait, no preemption and circular wait. All four must hold simultaneously for deadlock to be possible."], ["Handling methods", "Prevention breaks at least one necessary condition. Avoidance keeps the system in a safe state, commonly using the Banker's algorithm. Detection allows deadlock to occur and then identifies it."], ["Recovery", "After detection, recovery can terminate selected processes or preempt resources, while considering cost and the possibility of starvation."]],
        "formulae":[], "example":"If P1 holds R1 and waits for R2 while P2 holds R2 and waits for R1, neither can proceed; this forms a circular wait.",
        "applications":["Operating-system resource allocation", "Database transaction locking", "Concurrent software"],
        "revision":["Remember all four necessary conditions.", "Differentiate prevention, avoidance and detection.", "A safe state is not the same as a deadlocked state.", "Banker's algorithm is an avoidance technique."]}),
      (["sql join", "sql joins", "join"], {
        "keys":["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL OUTER JOIN", "Join conditions and keys"],
        "details":[["INNER JOIN", "Returns rows that have matching values in both tables."], ["LEFT JOIN", "Returns every row from the left table and matching rows from the right table; unmatched right-side values are NULL."], ["RIGHT JOIN", "Returns every row from the right table and matching rows from the left table."], ["FULL OUTER JOIN", "Returns matched rows plus unmatched rows from both tables when the DBMS supports it."]],
        "formulae":["Typical syntax: SELECT columns FROM A JOIN B ON A.key = B.key;"],
        "example":"To combine Student and Department, join them using a shared department_id. INNER JOIN shows students with a matching department; LEFT JOIN can also keep students whose department is missing.",
        "applications":["Combining normalized tables", "Reports across customers and orders", "Student/course databases"],
        "revision":["Identify which table must keep unmatched rows.", "Use ON for the relationship between tables.", "Ambiguous column names should be qualified with the table name or alias."]}),
      (["linked list"], {
        "keys":["Node structure", "Singly linked list", "Insertion and deletion", "Traversal and search", "Doubly and circular lists"],
        "details":[["Structure", "A linked list stores data in nodes. Each node contains data and one or more links to other nodes; nodes do not need contiguous memory."], ["Singly linked list", "Each node points to the next node. The head identifies the first node and the last node points to NULL."], ["Operations", "Traversal follows links from the head. Insertion and deletion change links rather than shifting a block of array elements."], ["Variants", "A doubly linked list adds a previous link. A circular list connects the last node back to the first node."]],
        "formulae":["Typical node: struct Node { int data; struct Node *next; };"],
        "example":"To insert at the beginning: create a node, set newNode->next = head, then set head = newNode.",
        "applications":["Dynamic collections", "Stacks and queues", "Adjacency lists", "Navigation structures"],
        "revision":["Draw pointer changes for insertion/deletion.", "Handle an empty list separately.", "Do not lose the next-node address while changing links.", "Know singly vs doubly vs circular differences."]}),
      (["cpu scheduling", "scheduling algorithm"], {
        "keys":["Scheduling criteria", "FCFS", "SJF/SRTF", "Priority scheduling", "Round Robin"],
        "details":[["Purpose", "CPU scheduling selects a ready process for execution when multiple processes are waiting for the processor."], ["FCFS", "First Come First Serve executes in arrival order and is simple but may produce the convoy effect."], ["SJF and SRTF", "Shortest Job First selects the smallest CPU burst; SRTF is its preemptive form."], ["Round Robin", "Round Robin gives each ready process a fixed time quantum and is commonly used to explain time-sharing systems."]],
        "formulae":["Turnaround time = Completion time − Arrival time", "Waiting time = Turnaround time − Burst time", "Response time = First CPU start time − Arrival time"],
        "example":"In FCFS, processes are placed in arrival order. Each process waits for the burst times of processes scheduled before it.",
        "applications":["Batch systems", "Interactive time sharing", "Priority-based workloads"],
        "revision":["Know preemptive vs non-preemptive algorithms.", "Practise Gantt charts.", "Calculate waiting and turnaround times carefully.", "Understand the effect of the Round Robin time quantum."]}),
      (["operating system", "process synchronization", "memory management", "virtual memory", "paging"], {
        "keys":["Processes and threads", "CPU scheduling", "Synchronization", "Memory management", "Files and I/O"],
        "details":[["Process management", "The OS creates, schedules and terminates processes and maintains information such as process state and CPU context."], ["Synchronization", "Concurrent processes may share data, so mechanisms such as mutexes and semaphores protect critical sections and coordinate execution."], ["Memory management", "The OS tracks memory use and maps program addresses to physical memory. Paging and virtual memory allow flexible allocation."], ["System services", "The OS also manages files, devices, protection, user interfaces and system calls."]],
        "formulae":[], "example":"When a running process blocks for I/O, the scheduler can select another ready process and the OS performs a context switch.",
        "applications":["Process execution", "Resource sharing", "Memory protection", "Device and file management"],
        "revision":["Distinguish process from program and thread.", "Know process states and context switching.", "Connect synchronization concepts to race conditions.", "Relate paging to virtual memory."]}),
      (["probability", "statistics"], {
        "keys":["Sample space and events", "Probability rules", "Conditional probability", "Random variables", "Descriptive statistics"],
        "details":[["Probability", "Probability quantifies uncertainty on a scale from 0 to 1. Events are subsets of a sample space containing possible outcomes."], ["Conditional probability", "Conditional probability measures the chance of A given that B has occurred and is central to Bayes' theorem."], ["Statistics", "Statistics summarizes and analyses observed data using measures such as mean, median, variance and standard deviation."], ["Distributions", "Probability distributions describe how probability is assigned to possible values of a random variable."]],
        "formulae":["P(A|B) = P(A∩B) / P(B)", "Mean = sum of observations / number of observations", "Variance measures average squared deviation from the mean"],
        "example":"For a fair six-sided die, P(even)=3/6=1/2 because {2,4,6} are three of the six equally likely outcomes.",
        "applications":["Data analysis", "Machine learning", "Reliability", "Decision making under uncertainty"],
        "revision":["Define the sample space first.", "Check whether events are independent or mutually exclusive.", "Know when to use conditional probability.", "Interpret mean and spread together."]}),
      (["linear algebra", "algebra", "mathematics"], {
        "keys":["Variables and equations", "Vectors and matrices", "Systems of equations", "Transformations", "Problem-solving methods"],
        "details":[["Core idea", "Algebra represents quantities and relationships symbolically. Linear algebra focuses on vectors, matrices, linear equations and transformations."], ["Vectors", "A vector represents an ordered set of components and can model direction, magnitude or features."], ["Matrices", "Matrices organize values in rows and columns and are used to represent systems of equations and linear transformations."], ["Systems", "Systems of linear equations can be solved using substitution, elimination or matrix-based methods."]],
        "formulae":["For Ax=b, A is the coefficient matrix, x the unknown vector and b the result vector."],
        "example":"The equations x+y=5 and x−y=1 can be added to obtain 2x=6, so x=3 and y=2.",
        "applications":["Computer graphics", "Machine learning", "Engineering models", "Data transformations"],
        "revision":["Keep matrix dimensions consistent.", "Practise solving small systems by hand.", "Understand vectors geometrically as well as numerically."]}),
      (["sql", "dbms", "database", "relational algebra", "er model"], {
        "keys":["Relational model", "Keys and constraints", "SQL operations", "Normalization and transactions", "Indexes and query processing"],
        "details":[["Relational data", "A relational database stores structured data in tables made of rows and columns. Relationships are represented using keys."], ["Keys", "Primary keys uniquely identify rows; foreign keys reference keys in related tables and help maintain referential integrity."], ["SQL", "SQL supports data definition, querying and modification using commands such as CREATE, SELECT, INSERT, UPDATE and DELETE."], ["Design and reliability", "Normalization reduces undesirable redundancy, while transactions group operations and aim to preserve database consistency."]],
        "formulae":["Core query form: SELECT columns FROM table WHERE condition;"],
        "example":"A Student table can use roll_no as a primary key and department_id as a foreign key referencing a Department table.",
        "applications":["Student information systems", "Banking and transactions", "Web application storage", "Reporting"],
        "revision":["Know primary vs foreign keys.", "Differentiate DDL, DML and query operations.", "Understand why normalization is used.", "Relate transactions to consistency."]}),
      (["machine learning", "supervised", "unsupervised", "reinforcement", "recommendation"], {
        "keys":["Data and features", "Training and testing", "Learning types", "Model evaluation", "Generalization"],
        "details":[["Learning from data", "Machine learning builds models that identify patterns from examples rather than relying only on explicitly programmed rules."], ["Supervised learning", "Supervised learning trains on labelled examples for tasks such as classification and regression."], ["Unsupervised learning", "Unsupervised learning explores unlabelled data to find structure, such as clusters or lower-dimensional representations."], ["Evaluation", "A model should be evaluated on data not used for training so that performance reflects generalization rather than memorization."]],
        "formulae":["Typical workflow: data → preprocessing → training → validation/testing → evaluation → improvement"],
        "example":"A spam classifier can learn from emails labelled spam/not-spam and then predict the class of unseen emails.",
        "applications":["Recommendation", "Classification", "Forecasting", "Pattern recognition"],
        "revision":["Differentiate features from labels.", "Know supervised vs unsupervised learning.", "Avoid evaluating only on training data.", "Choose evaluation measures that fit the task."]}),
      (["artificial intelligence", " ai ", "intelligent agent", "knowledge representation"], {
        "keys":["Intelligent agents", "Search and problem solving", "Knowledge representation", "Reasoning and learning", "AI applications"],
        "details":[["Intelligent agents", "An intelligent agent perceives its environment and selects actions intended to achieve a goal."], ["Search", "AI search represents possible states and explores actions that lead from an initial state toward a goal state."], ["Knowledge and reasoning", "Knowledge representation stores facts and relationships in forms that a system can use for inference and decision making."], ["Learning", "Modern AI often combines reasoning or search with machine-learning methods that learn patterns from data."]],
        "formulae":[], "example":"A route-planning agent can treat locations as states, roads as actions and the destination as the goal, then search for an appropriate path.",
        "applications":["Search and planning", "Language systems", "Computer vision", "Recommendation and automation"],
        "revision":["Know agent, environment, state, action and goal.", "Differentiate search-based reasoning from learning from data.", "Use concrete examples when explaining AI applications."]}),
      (["python"], {
        "keys":["Syntax and data types", "Control flow and functions", "Collections", "Modules and files", "Object-oriented programming"],
        "details":[["Language basics", "Python is a high-level programming language with readable syntax and dynamic typing. Variables refer to objects and indentation defines code blocks."], ["Functions", "Functions package reusable behaviour, accept parameters and can return values. Modules organize reusable functions, classes and constants."], ["Collections", "Lists, tuples, sets and dictionaries provide different ways to organize data."], ["OOP and files", "Classes define objects with data and behaviour, while file handling allows programs to persist and retrieve information."]],
        "formulae":["Function form: def name(parameters): ... return value"],
        "example":"def square(x): return x*x defines a reusable function; square(5) returns 25.",
        "applications":["Automation", "Data analysis", "Web development", "AI and machine learning"],
        "revision":["Practise indentation and control flow.", "Know mutable vs immutable collections.", "Break programs into functions.", "Handle file/resource errors appropriately."]}),
      (["java", "oop", "inheritance", "polymorphism", "encapsulation", "overriding"], {
        "keys":["Classes and objects", "Encapsulation", "Inheritance", "Polymorphism", "Interfaces and exceptions"],
        "details":[["Classes and objects", "A class defines fields and methods; an object is an instance created from that class."], ["Encapsulation", "Encapsulation groups data and behaviour and controls access to internal state through access modifiers and methods."], ["Inheritance", "Inheritance allows a subclass to reuse and extend members of a parent class."], ["Polymorphism", "With method overriding, a parent reference can call a subclass implementation at runtime, demonstrating runtime polymorphism."]],
        "formulae":["Inheritance form: class Child extends Parent { ... }"],
        "example":"If Dog extends Animal and overrides sound(), an Animal reference pointing to a Dog object calls Dog's sound() implementation.",
        "applications":["Reusable software models", "GUI/application frameworks", "Backend systems", "Android development"],
        "revision":["Differentiate class from object.", "Know overloading vs overriding.", "Understand IS-A inheritance.", "Use interfaces to describe behaviour contracts."]}),
      ([" c programming", "c programming", "pointer", "structures", "recursion"], {
        "keys":["Data types and operators", "Control statements and functions", "Pointers", "Structures", "Dynamic memory and files"],
        "details":[["C fundamentals", "C is a procedural language in which programs are built from functions, variables, expressions and control statements."], ["Pointers", "A pointer stores a memory address. The address-of operator obtains an address and dereferencing accesses the value at that address."], ["Structures", "A structure groups related values of potentially different data types under one user-defined type."], ["Dynamic memory", "Functions such as malloc, calloc, realloc and free manage memory obtained at runtime."]],
        "formulae":["Pointer pattern: int x=10; int *p=&x; then *p accesses x."],
        "example":"A Student structure can group name, roll number and mark; a pointer to the structure can access members using the -> operator.",
        "applications":["Systems programming", "Data structures", "Embedded software", "Memory-efficient programs"],
        "revision":["Trace pointer values carefully.", "Match allocated memory with free().", "Know . versus -> for structures.", "Practise function parameter passing."]}),
      (["network", "osi", "tcp", "ip addressing", "routing"], {
        "keys":["Network models", "Addressing", "Protocols", "Routing and switching", "Security"],
        "details":[["Communication", "Computer networks connect devices so that data and resources can be exchanged using agreed protocols."], ["Layered models", "OSI and TCP/IP divide communication into layers, helping separate responsibilities such as application services, transport, routing and link delivery."], ["Addressing", "IP addresses identify network interfaces logically; subnetting divides address space into smaller networks."], ["Routing", "Routers forward packets between networks, while switches primarily forward frames within local networks."]],
        "formulae":[], "example":"When a browser contacts a remote web server, application data is carried through transport and network layers before frames are sent over the local link.",
        "applications":["Internet communication", "LANs", "Cloud services", "Secure remote access"],
        "revision":["Know the purpose of each OSI layer.", "Differentiate IP and MAC addressing.", "Understand router vs switch roles.", "Relate common protocols to their layers."]}),
      (["8086", "coa", "computer architecture", "instruction cycle", "memory organization"], {
        "keys":["Processor functional units", "Registers", "Instruction cycle", "Memory and buses", "8086 organization"],
        "details":[["Processor organization", "A processor uses an ALU, control unit and registers to execute instructions and coordinate data movement."], ["Instruction cycle", "Instruction processing normally involves fetching an instruction, decoding it, obtaining operands, executing the operation and storing the result."], ["Buses and memory", "Address, data and control buses carry locations, values and control signals between processor, memory and I/O."], ["8086", "The 8086 separates the Bus Interface Unit and Execution Unit and uses segmented memory with registers such as CS, DS, SS and ES."]],
        "formulae":["8086 physical address = segment × 16 + offset"],
        "example":"For segment 1000H and offset 0020H, the physical address is 10020H.",
        "applications":["Instruction execution", "Memory interfacing", "Microprocessor programming", "Computer-system design"],
        "revision":["Know BIU vs EU.", "Revise register purposes.", "Trace fetch-decode-execute clearly.", "Differentiate address, data and control buses."]}),
      (["html", "css", "javascript", "web development", "flask", "rest api"], {
        "keys":["HTML structure", "CSS presentation", "JavaScript behaviour", "Client-server interaction", "Responsive and API-based design"],
        "details":[["HTML", "HTML gives a web page semantic structure using elements for headings, text, forms, tables, links and other content."], ["CSS", "CSS controls presentation and layout. Flexbox, Grid and media queries are common tools for responsive interfaces."], ["JavaScript", "JavaScript adds behaviour in the browser by manipulating the DOM, responding to events and making asynchronous requests."], ["Backend and APIs", "Backend frameworks such as Flask receive HTTP requests, execute server logic and return HTML or structured data such as JSON."]],
        "formulae":["Typical web flow: browser request → route/API → application logic → response"],
        "example":"A search form can send a query to Flask; Flask searches local data and returns results that the browser renders.",
        "applications":["Websites", "Web applications", "REST APIs", "Responsive interfaces"],
        "revision":["Keep HTML structure, CSS presentation and JS behaviour conceptually separate.", "Know common HTTP request methods.", "Use semantic HTML where appropriate.", "Understand DOM events and asynchronous requests."]}),
    ]

    profile = next((p for words,p in profiles if any(w in blob for w in words)), None)
    if profile is None:
        profile = {
          "keys":[f"Definition and purpose of {title}", f"Main concepts in {topic}", "How the concept works", "Examples and practical use", "Important points and limitations"],
          "details":[["Core idea", desc or f"{title} is an important concept within {topic}. Begin by understanding its definition, purpose and terminology."], ["How to study it", f"Break {title} into its main components, understand the role of each component, and then connect them using a worked example or application."], ["Deeper understanding", f"For {level.lower()} study, compare related concepts, identify common mistakes and practise explaining the process in your own words."]],
          "formulae":[], "example":f"Use a simple {title} example from your course material and trace it step by step, naming each important component and the result of each step.",
          "applications":[f"Applications within {topic}", "Problem solving", "Practical or implementation-based exercises"],
          "revision":["Learn the definition and purpose.", "List the main components or steps.", "Practise at least one example.", "Compare it with closely related concepts."]}

    overview = desc or f"{title} is a topic within {topic}. This local AURAVIS document explains its core ideas, examples, applications and revision points."
    study = f"Study {title} in this order: understand the overview, learn each core concept, work through the example, then use the revision checklist. The document is designed for {level.lower()} level and is available from local AURAVIS data without an internet connection."
    return {"title":title,"topic":topic,"level":level,"overview":overview,"study":study,
            "keys":profile["keys"],"details":profile["details"],"formulae":profile["formulae"],
            "example":profile["example"],"applications":profile["applications"],"revision":profile["revision"]}


def detect_video_language(query="", selected_language="en"):
    """Choose the preferred YouTube language. English is the default.
    A non-English UI selection or clearly non-English script overrides it.
    """
    q = str(query or "")
    selected = str(selected_language or "en").lower()
    # Script detection lets Search Fusion still choose the user's language even
    # when the language selector was left on English.
    script_ranges = [
        ("ta", "\u0b80", "\u0bff"), ("hi", "\u0900", "\u097f"),
        ("te", "\u0c00", "\u0c7f"), ("kn", "\u0c80", "\u0cff"),
        ("ml", "\u0d00", "\u0d7f"), ("bn", "\u0980", "\u09ff"),
        ("gu", "\u0a80", "\u0aff"), ("pa", "\u0a00", "\u0a7f"),
    ]
    for code, lo, hi in script_ranges:
        if any(lo <= ch <= hi for ch in q):
            return code
    if selected and selected != "en":
        return selected
    return "en"


def _youtube_language_matches(audio_language, wanted):
    """Return True only when YouTube explicitly reports the requested audio language."""
    audio = str(audio_language or "").strip().lower().replace("_", "-")
    wanted = str(wanted or "en").strip().lower().replace("_", "-")
    if not audio:
        return False
    return audio == wanted or audio.startswith(wanted + "-")


def youtube_video_for(item, query="", language="en"):
    """Return an embeddable educational YouTube video with verified audio language.

    search.list's relevanceLanguage is only a relevance hint, so AURAVIS searches
    several candidates and then validates snippet.defaultAudioLanguage with
    videos.list before choosing a video. English is the default; a detected
    non-English search language is tried first, with verified English fallback.
    """
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        return None
    preferred = detect_video_language(query, language)
    language_names = {
        "en":"English", "ta":"Tamil", "hi":"Hindi", "es":"Spanish",
        "te":"Telugu", "kn":"Kannada", "ml":"Malayalam", "bn":"Bengali",
        "gu":"Gujarati", "pa":"Punjabi"
    }
    attempts = [preferred] + (["en"] if preferred != "en" else [])

    for lang in attempts:
        lang_name = language_names.get(lang, lang)
        search_q = f'{item.get("title", "")} {item.get("topic", "")} {lang_name} educational tutorial'
        params = urlencode({
            "part":"snippet", "q":search_q, "type":"video", "maxResults":10,
            "videoEmbeddable":"true", "videoSyndicated":"true",
            "safeSearch":"strict", "relevanceLanguage":lang, "key":api_key
        })
        try:
            req = Request("https://www.googleapis.com/youtube/v3/search?" + params, headers={"User-Agent":"AURAVIS/1.0"})
            with urlopen(req, timeout=6) as r:
                import json
                search_data = json.loads(r.read().decode("utf-8"))
            ids = [x.get("id", {}).get("videoId") for x in (search_data.get("items") or [])]
            ids = [x for x in ids if x]
            if not ids:
                continue

            # Validate the actual spoken/default audio language. This is stricter
            # than relevanceLanguage and prevents Hindi/Hinglish results from
            # being selected for ordinary English searches when metadata exists.
            details_params = urlencode({
                "part":"snippet,status", "id":",".join(ids), "key":api_key
            })
            dreq = Request("https://www.googleapis.com/youtube/v3/videos?" + details_params, headers={"User-Agent":"AURAVIS/1.0"})
            with urlopen(dreq, timeout=6) as r:
                details = json.loads(r.read().decode("utf-8"))

            candidates = []
            for v in (details.get("items") or []):
                sn = v.get("snippet", {})
                status = v.get("status", {})
                if status.get("embeddable") is False:
                    continue
                audio = sn.get("defaultAudioLanguage", "")
                if not _youtube_language_matches(audio, lang):
                    continue
                candidates.append(v)

            if candidates:
                v = candidates[0]
                sn = v.get("snippet", {})
                vid = v.get("id")
                return {
                    "id":vid,
                    "embed":f"https://www.youtube-nocookie.com/embed/{vid}?rel=0",
                    "title":sn.get("title", "Learning video"),
                    "channel":sn.get("channelTitle", "YouTube"),
                    "language":lang,
                    "language_name":language_names.get(lang, lang.upper()),
                    "audio_language":sn.get("defaultAudioLanguage", lang),
                    "language_verified":True
                }
        except Exception:
            continue
    return None

def norm(s):
    s = str(s or "").lower()
    aliases = {
        "கணிதம்": "math mathematics",
        "கணினி": "computer computing",
        "படம்": "movie film",
        "திரைப்படம்": "movie film",
        "மூவி": "movie film",
        "मूवी": "movie film",
        "गणित": "math mathematics",
        "फिल्म": "movie film",
        "சி": "c programming",
        "காமெடி": "comedy",
        "कॉमेडी": "comedy",
    }
    for k, v in aliases.items():
        if k in s:
            s += " " + v
    s = s.replace("c programming", " c ").replace("c language", " c ")
    s = re.sub(r"[^a-z0-9+#.\-\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(s):
    return [x for x in re.findall(r"[a-z0-9+#.]+", norm(s)) if len(x) > 1]


def item_text(category, row):
    if category == "education":
        return " ".join([row.get("title", ""), row.get("topic", ""), row.get("description", ""), row.get("difficulty", "")])
    return " ".join([row.get("title", ""), row.get("genre", ""), row.get("description", ""), row.get("director", "")])


SEMANTIC_ALIASES = {
    "cpu scheduling": ["cpu", "fcfs", "round robin", "process scheduling", "waiting time", "turnaround time"],
    "deadlock": ["banker algorithm", "mutual exclusion", "hold and wait", "circular wait"],
    "linked list": ["singly linked list", "doubly linked list", "nodes", "pointers"],
    "data structures": ["dsa", "stack", "queue", "linked list", "tree", "graph"],
    "database": ["dbms", "sql", "query", "relational database"],
    "machine learning": ["ml", "classification", "regression", "model training"],
    "artificial intelligence": ["ai", "machine learning", "intelligent systems"],
    "computer organization": ["coa", "processor", "memory", "instruction", "8086"],
    "operating system": ["os", "process", "thread", "scheduling", "deadlock"],
    "web development": ["html", "css", "javascript", "frontend", "web"],
    "science fiction": ["sci-fi", "space", "future", "technology"],
    "romantic": ["romance", "love"],
    "funny": ["comedy", "humor"],
    "scary": ["horror", "supernatural"],
}

def semantic_expand(query):
    """Tiny offline intent expansion: deterministic, dependency-free and safe to fall back."""
    base = norm(query)
    extras = []
    for concept, aliases in SEMANTIC_ALIASES.items():
        terms = [concept] + aliases
        if any(norm(t) in base or base in norm(t) for t in terms if len(norm(t)) >= 3):
            extras.extend(terms)
    # keep it deliberately small so semantic-lite never overwhelms exact search
    return " ".join(dict.fromkeys([query] + extras[:6]))

def search_local(query, category, limit=12):
    """Fast local search. No external API and no extra Python packages required."""
    rows = load(category)
    q = norm(query)
    expanded_query = semantic_expand(query)
    qt = tokens(expanded_query)
    if not qt:
        return []
    results = []
    for row in rows:
        text = norm(item_text(category, row))
        title = norm(row.get("title", ""))
        text_words = set(tokens(text))
        title_words = set(tokens(title))
        hits = sum(1 for term in qt if term in text_words or term in text)
        # Single-letter programming searches (especially C) must match a real token,
        # not every word containing the letter c.
        if any(len(term) == 1 for term in qt):
            hits = sum(1 for term in qt if term in text_words)
        title_hits = sum(1 for term in qt if term in title_words)
        phrase = 1 if q and q in text else 0
        fuzzy = 0
        for term in qt:
            for word in tokens(row.get("title", "")):
                if len(term) >= 4 and (word.startswith(term) or term.startswith(word)):
                    fuzzy += 1
                    break
        if hits == 0 and fuzzy == 0:
            continue
        score = 45 + (hits / max(1, len(qt))) * 30 + title_hits * 12 + phrase * 8 + fuzzy * 4
        item = dict(row)
        item["score"] = round(min(99, score), 1)
        item["search_score"] = round(min(100, 45 + (hits / max(1, len(qt))) * 55), 1)
        item["preference_score"] = 0.0
        results.append(item)
    return sorted(results, key=lambda x: float(x["score"]), reverse=True)[:limit]



_offline_vision_pipe = None

def _clean_vision_query(text):
    text = re.sub(r"[^A-Za-z0-9+#. -]+", " ", str(text or ""))
    text = re.sub(r"\\s+", " ", text).strip()
    # Prefer useful programming / education concepts when a caption contains them.
    known = [
        "python programming", "java programming", "c++ programming", "c programming",
        "data structures", "machine learning", "artificial intelligence", "mathematics",
        "computer science", "programming", "algorithm", "database", "operating system",
        "space", "science fiction", "comedy", "movie"
    ]
    low = text.lower()
    for phrase in known:
        if phrase in low:
            return phrase.title() if phrase != "c++ programming" else "C++ Programming"
    words = [w for w in text.split() if len(w) > 2][:8]
    return " ".join(words)[:160] or "image search"

def offline_vision_query_from_image(raw, mime="image/jpeg"):
    """Caption an image with a locally cached BLIP model, then turn the caption into a search query.
    After the one-time model download, this path makes no API/network call.
    """
    global _offline_vision_pipe
    try:
        from PIL import Image
        from transformers import pipeline
        import io
    except Exception as exc:
        raise RuntimeError(
            "Offline Vision is not installed yet. Run: python -m pip install -r requirements.txt, "
            "then: python download_offline_vision.py"
        ) from exc

    model_name = os.getenv("AURAVIS_OFFLINE_VISION_MODEL", "Salesforce/blip-image-captioning-base")
    if _offline_vision_pipe is None:
        try:
            # local_files_only=True guarantees that an offline search never silently uses internet.
            _offline_vision_pipe = pipeline(
                "image-to-text", model=model_name
            )
        except Exception as exc:
            raise RuntimeError(
                "Offline Vision model is not cached on this computer yet. While online, run: "
                "python download_offline_vision.py. After that, image search works offline."
            ) from exc
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    result = _offline_vision_pipe(image, max_new_tokens=35)
    caption = result[0].get("generated_text", "") if result else ""
    return _clean_vision_query(caption), caption

def openai_vision_query_from_bytes(raw, mime):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    from openai import OpenAI
    data_url = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=os.getenv("AURAVIS_VISION_MODEL", "gpt-4.1-mini"),
        input=[{"role":"user","content":[
            {"type":"input_text","text":"Identify the main searchable subject of this image. Return only a concise search query of 2 to 8 words, with no punctuation or explanation."},
            {"type":"input_image","image_url":data_url}
        ]}]
    )
    return _clean_vision_query(response.output_text), (response.output_text or "").strip()

def vision_query_from_image(file_storage):
    """AURAVIS hybrid vision: local/offline first by default, OpenAI optional fallback."""
    raw = file_storage.read()
    if not raw:
        raise ValueError("The uploaded image is empty.")
    if len(raw) > app.config["MAX_CONTENT_LENGTH"]:
        raise ValueError("Image is too large. Maximum size is 4 MB.")
    mime = file_storage.mimetype or mimetypes.guess_type(file_storage.filename or "image.jpg")[0] or "image/jpeg"
    if not mime.startswith("image/"):
        raise ValueError("Please upload a valid image file.")

    mode = os.getenv("AURAVIS_VISION_MODE", "local").strip().lower()
    errors = []
    if mode in ("local", "hybrid"):
        try:
            query, caption = offline_vision_query_from_image(raw, mime)
            return query, "offline", caption
        except Exception as exc:
            errors.append(str(exc))
            if mode == "local":
                raise
    if mode in ("openai", "hybrid"):
        try:
            query, caption = openai_vision_query_from_bytes(raw, mime)
            return query, "openai", caption
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError("Vision search failed. " + " | ".join(errors))

GOAL_HINTS = {
    "learn": ["tutorial", "fundamentals", "introduction", "basics", "guide", "concept"],
    "exam": ["definition", "exam", "question", "notes", "summary", "important", "data structures", "operating"],
    "build": ["project", "programming", "implementation", "code", "development", "practical"],
    "research": ["advanced", "analysis", "research", "algorithm", "machine learning", "artificial intelligence"],
    "explore": ["overview", "discovery", "movie", "comedy", "space", "sci-fi"]
}

def get_goal(uid):
    c=db(); r=c.execute("SELECT goal,level FROM user_goals WHERE user_id=?",(uid,)).fetchone(); c.close()
    return {"goal": r["goal"], "level": r["level"]} if r else {"goal":"learn","level":"beginner"}

def set_goal(uid, goal, level):
    if goal not in GOAL_HINTS: goal="learn"
    if level not in ("beginner","intermediate","advanced"): level="beginner"
    c=db(); c.execute("""INSERT INTO user_goals(user_id,goal,level) VALUES(?,?,?)
      ON CONFLICT(user_id) DO UPDATE SET goal=excluded.goal,level=excluded.level,updated_at=CURRENT_TIMESTAMP""",(uid,goal,level)); c.commit(); c.close()

def goal_rerank(results, category, goal, level):
    hints=GOAL_HINTS.get(goal,[])
    out=[]
    for item in results:
        x=dict(item); text=norm(item_text(category,x))
        goal_boost=sum(2.5 for h in hints if h in text)
        level_boost=0
        if category=="education":
            difficulty=norm(x.get("difficulty",""))
            if level=="beginner" and any(k in difficulty for k in ("beginner","easy")): level_boost=5
            elif level=="intermediate" and "intermediate" in difficulty: level_boost=5
            elif level=="advanced" and "advanced" in difficulty: level_boost=5
        x["goal_score"]=round(min(15,goal_boost+level_boost),1)
        x["score"]=round(min(99,float(x.get("score",0))+x["goal_score"]),1)
        reasons=[]
        if x["goal_score"]>0: reasons.append(f"fits {goal.title()} mode")
        if float(x.get("preference_score",0))>0: reasons.append("matches your learned interests")
        if not reasons: reasons.append("strong query match")
        x["why"]=" • ".join(reasons)
        out.append(x)
    return sorted(out,key=lambda z:float(z["score"]),reverse=True)

def search_journey(uid, limit=6):
    c=db(); rows=c.execute("SELECT query,category,created_at FROM searches WHERE user_id=? ORDER BY id DESC LIMIT ?",(uid,limit)).fetchall(); c.close()
    seen=[]
    for r in rows:
        key=(r["query"].lower(),r["category"])
        if key not in [(x["query"].lower(),x["category"]) for x in seen]: seen.append(dict(r))
    return list(reversed(seen))

def knowledge_map(uid):
    rows=get_activity(uid,250); scores={}
    stop={"programming","learning","movie","film","with","using","introduction","fundamentals"}
    for r in rows:
        if r["category"]!="education": continue
        w={"search":1,"click":2,"view":3,"like":5}.get(r["action"],0)
        for term in tokens((r["query"] or "")+" "+(r["title"] or "")):
            if term not in stop: scores[term]=scores.get(term,0)+w
    top=sorted(scores.items(),key=lambda x:x[1],reverse=True)[:6]
    return [{"topic":k.title(),"level":"Advanced" if v>=14 else "Intermediate" if v>=7 else "Learning","score":v} for k,v in top]

def feedback_map(uid):
    c = db(); rows = c.execute("SELECT category,content_id,action FROM feedback WHERE user_id=?", (uid,)).fetchall(); c.close()
    return {(r["category"], str(r["content_id"])): r["action"] for r in rows}


def get_activity(uid, limit=100):
    c = db(); rows = c.execute("SELECT * FROM activity WHERE user_id=? ORDER BY id DESC LIMIT ?", (uid, limit)).fetchall(); c.close()
    return rows


def record(uid, category, action, content_id="", title="", query=""):
    c = db()
    c.execute("INSERT INTO activity(user_id,category,action,content_id,title,query) VALUES(?,?,?,?,?,?)",
              (uid, category, action, content_id, title, query))
    c.commit(); c.close()


def preference_profile(uid, category):
    """Create a simple explainable profile from searches, views, clicks and likes."""
    rows = get_activity(uid, 200)
    weights = {"search": 1, "click": 2, "view": 3, "like": 5, "not_interested": -5, "preference_removed": 0}
    terms = {}
    for r in rows:
        if r["category"] != category:
            continue
        w = weights.get(r["action"], 0)
        if w <= 0:
            continue
        text = r["query"] or r["title"]
        for term in tokens(text):
            terms[term] = terms.get(term, 0) + w
        if r["content_id"] and r["action"] in ("view", "click", "like"):
            item = next((x for x in load(category) if str(x.get("id")) == str(r["content_id"])), None)
            if item:
                for term in tokens(item_text(category, item)):
                    terms[term] = terms.get(term, 0) + w
    ranked = sorted(terms.items(), key=lambda x: x[1], reverse=True)[:10]
    if not ranked:
        return {"ready": False, "message": "Search and interact with more content to teach AURAVIS.", "keywords": [], "activity_count": 0}
    top = max(v for _, v in ranked)
    return {"ready": True, "message": "AURAVIS learned from your searches, views and feedback.",
            "keywords": [{"term": k, "score": round(v / top, 3)} for k, v in ranked],
            "activity_count": sum(1 for r in rows if r["category"] == category)}


def personalized(results, category, uid):
    fm = feedback_map(uid)
    profile = preference_profile(uid, category)
    profile_terms = {x["term"]: x["score"] for x in profile["keywords"]}
    out = []
    for item in results:
        cid = str(item.get("id", ""))
        action = fm.get((category, cid))
        if action == "not_interested":
            continue
        text = norm(item_text(category, item))
        boost = sum(v * 8 for term, v in profile_terms.items() if term in text)
        if action == "like":
            boost += 10
        item["preference_score"] = round(min(35, boost), 1)
        item["score"] = round(min(99, float(item["score"]) + item["preference_score"]), 1)
        out.append(item)
    return sorted(out, key=lambda x: float(x["score"]), reverse=True)


def recommendations(uid, category, limit=6):
    profile = preference_profile(uid, category)
    if not profile["ready"]:
        return []
    fm = feedback_map(uid)
    terms = {x["term"]: x["score"] for x in profile["keywords"]}
    candidates = []
    for item in load(category):
        cid = str(item.get("id", ""))
        if fm.get((category, cid)) == "not_interested":
            continue
        text = norm(item_text(category, item))
        score = sum(v for term, v in terms.items() if term in text)
        if fm.get((category, cid)) == "like":
            score += 2
        if score > 0:
            x = dict(item); x["score"] = round(min(99, score * 10), 1); candidates.append(x)
    return sorted(candidates, key=lambda x: float(x["score"]), reverse=True)[:limit]


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    u = current_user()
    if request.method == "POST":
        category = request.form.get("category", "education")
        query = request.form.get("query", "").strip()
        language = request.form.get("language", "en")
        goal = request.form.get("goal", "learn")
        level = request.form.get("level", "beginner")
    else:
        category = request.args.get("category", "education")
        query = request.args.get("q", "").strip()
        language = request.args.get("language", "en")
        saved_goal = get_goal(u["id"])
        goal = request.args.get("goal", saved_goal["goal"])
        level = request.args.get("level", saved_goal["level"])
    if category not in ("education", "movies"):
        category = "education"
    set_goal(u["id"], goal, level)
    results = []
    if query:
        record(u["id"], category, "search", query=query)
        c = db(); c.execute("INSERT INTO searches(user_id,query,category,language) VALUES(?,?,?,?)", (u["id"], query, category, language)); c.commit(); c.close()
        results = personalized(search_local(query, category), category, u["id"])
        results = goal_rerank(results, category, goal, level)
    activity = get_activity(u["id"], 100)
    profiles = {"education": preference_profile(u["id"], "education"), "movies": preference_profile(u["id"], "movies")}
    recs = {"education": recommendations(u["id"], "education"), "movies": recommendations(u["id"], "movies")}
    return render_template("index.html", user=u, results=results, query=query, category=category, language=language,
                           history=[r for r in activity if r["action"] == "search"], prefs=feedback_map(u["id"]), profiles=profiles, recommendations=recs,
                           goal=goal, level=level, journey=search_journey(u["id"]), knowledge=knowledge_map(u["id"]), offline_ready=True)


@app.post("/api/search")
@login_required
def api_search():
    try:
        d = request.get_json(silent=True) or {}
        query = str(d.get("query", "")).strip()
        category = str(d.get("category", "education")).lower()
        if category not in ("education", "movies"): category = "education"
        if not query: return jsonify(ok=False, error="Enter a search term.", results=[]), 400
        u = current_user(); goal=str(d.get("goal",get_goal(u["id"])["goal"])); level=str(d.get("level",get_goal(u["id"])["level"])); record(u["id"], category, "search", query=query)
        results = personalized(search_local(query, category), category, u["id"])
        results = goal_rerank(results, category, goal, level)
        return jsonify(ok=True, query=query, category=category, goal=goal, level=level, results=results)
    except Exception as e:
        app.logger.exception("SEARCH ERROR")
        return jsonify(ok=False, error=f"Search error: {type(e).__name__}: {e}", results=[]), 500


@app.post("/api/vision-search")
@login_required
def api_vision_search():
    try:
        image = request.files.get("image")
        if not image or not image.filename:
            return jsonify(ok=False, error="Choose an image first."), 400
        ext = image.filename.rsplit(".", 1)[-1].lower() if "." in image.filename else ""
        if ext not in ALLOWED_IMG:
            return jsonify(ok=False, error="Use PNG, JPG, JPEG, WEBP or GIF."), 400
        query, engine, caption = vision_query_from_image(image)
        return jsonify(ok=True, query=query, engine=engine, caption=caption)
    except Exception as e:
        app.logger.exception("VISION SEARCH ERROR")
        message = str(e)
        return jsonify(ok=False, error=message), 500


@app.post("/feedback")
@login_required
def feedback():
    category = request.form.get("category", "education")
    content_id = str(request.form.get("content_id", ""))
    title = request.form.get("title", "")
    action = request.form.get("action", "like")
    if category not in ("education", "movies") or action not in ("like", "not_interested"):
        return redirect(request.referrer or url_for("index"))
    u = current_user(); c = db()
    old = c.execute("SELECT action FROM feedback WHERE user_id=? AND category=? AND content_id=?", (u["id"], category, content_id)).fetchone()
    if old and old["action"] == action:
        c.execute("DELETE FROM feedback WHERE user_id=? AND category=? AND content_id=?", (u["id"], category, content_id))
        new_action = None
        activity_action = "preference_removed"
    else:
        c.execute("""INSERT INTO feedback(user_id,category,content_id,title,action) VALUES(?,?,?,?,?)
                     ON CONFLICT(user_id,category,content_id) DO UPDATE SET title=excluded.title,action=excluded.action,created_at=CURRENT_TIMESTAMP""",
                  (u["id"], category, content_id, title, action))
        new_action = action
        activity_action = action
    c.commit(); c.close()
    record(u["id"], category, activity_action, content_id, title)
    # Native form fallback means this works even if JavaScript is disabled.
    return redirect(request.referrer or url_for("index"))


@app.get("/api/history")
@login_required
def api_history():
    return jsonify(history=[dict(r) for r in get_activity(current_user()["id"], 100) if r["action"] == "search"])


@app.get("/api/preferences")
@login_required
def api_preferences():
    u = current_user(); c = db(); rows = c.execute("SELECT category,content_id,title,action,created_at FROM feedback WHERE user_id=? ORDER BY id DESC", (u["id"],)).fetchall(); c.close()
    return jsonify(preferences=[dict(r) for r in rows])


@app.post("/profile")
@login_required
def profile():
    u = current_user(); username = request.form.get("username", u["username"]).strip() or u["username"]
    avatar = u["avatar"] or ""
    f = request.files.get("avatar")
    if f and f.filename:
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext in ALLOWED_IMG:
            filename = f"avatar_{u['id']}_{int(time.time())}.{ext}"
            f.save(UPLOADS / filename); avatar = "/static/uploads/" + filename
    c = db(); c.execute("UPDATE users SET username=?,avatar=? WHERE id=?", (username, avatar, u["id"])); c.commit(); c.close()
    session["username"] = username
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
@login_required
def dashboard():
    u = current_user(); activity = get_activity(u["id"], 100)
    profiles = {"education": preference_profile(u["id"], "education"), "movies": preference_profile(u["id"], "movies")}
    return render_template("dashboard.html", user=u, activity=activity, stats={
        "searches": sum(1 for x in activity if x["action"] == "search"),
        "clicks": sum(1 for x in activity if x["action"] == "click"),
        "views": sum(1 for x in activity if x["action"] == "view"),
        "education": sum(1 for x in activity if x["category"] == "education"),
        "movies": sum(1 for x in activity if x["category"] == "movies")
    }, profiles=profiles, prefs=feedback_map(u["id"]))


@app.get("/api/learning-document/<content_id>")
@login_required
def api_learning_document(content_id):
    """Return the local AURAVIS learning document for an education result.

    This endpoint only reads the local education CSV, so the document remains
    available when the browser has no internet connection as long as Flask is
    running locally.
    """
    item = next((x for x in load("education") if str(x.get("id")) == str(content_id)), None)
    if not item:
        return jsonify(ok=False, error="Learning document not found."), 404
    lesson = education_lesson(item)
    return jsonify(ok=True, item={
        "id": str(item.get("id", "")),
        "title": str(item.get("title", "Learning Resource")),
        "topic": str(item.get("topic", "General")),
        "difficulty": str(item.get("difficulty", "General")),
        "description": str(item.get("description", ""))
    }, lesson=lesson)


@app.route("/content/<category>/<content_id>")
@login_required
def content(category, content_id):
    if category not in ("education", "movies"): return "Content not found", 404
    item = next((x for x in load(category) if str(x.get("id")) == str(content_id)), None)
    if not item: return "Content not found", 404
    u = current_user(); record(u["id"], category, "view", content_id, item.get("title", ""), request.args.get("q", ""))
    lesson = education_lesson(item) if category == "education" else None
    video = youtube_video_for(item, request.args.get("q", ""), request.args.get("language", "en")) if category == "education" else None
    return render_template("content.html", user=u, item=item, category=category, query=request.args.get("q", ""), lesson=lesson, video=video, youtube_enabled=bool(os.getenv("YOUTUBE_API_KEY", "").strip()))


@app.route("/open/<category>/<content_id>")
@login_required
def open_resource(category, content_id):
    item = next((x for x in load(category) if str(x.get("id")) == str(content_id)), None)
    if not item: return "Resource not found", 404
    u = current_user(); record(u["id"], category, "click", content_id, item.get("title", ""), request.args.get("query", ""))
    target = item.get("url", "")
    if not target:
        target = ("https://www.youtube.com/results?search_query=" + quote_plus(item.get("title", "") + " tutorial")) if category == "education" else ("https://www.imdb.com/find/?q=" + quote_plus(item.get("title", "")) + "&s=tt&ttype=ft")
    return redirect(target)


@app.route("/service-worker.js")
def service_worker():
    from flask import send_from_directory
    return send_from_directory(BASE / "static", "service-worker.js", mimetype="application/javascript")

@app.route("/offline")
def offline_page():
    return render_template("offline.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip(); password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 4: flash("Username must be at least 3 characters and password at least 4 characters.")
        else:
            c = db()
            try:
                c.execute("INSERT INTO users(username,password_hash) VALUES(?,?)", (username, generate_password_hash(password))); c.commit(); flash("Account created. Please login."); return redirect(url_for("login"))
            except sqlite3.IntegrityError: flash("That username is already registered.")
            finally: c.close()
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip(); password = request.form.get("password", "")
        c = db(); u = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone(); c.close()
        if u and check_password_hash(u["password_hash"], password):
            session["user_id"] = u["id"]; session["username"] = u["username"]; return redirect(url_for("index"))
        flash("Invalid username or password.")
    return render_template("login.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
