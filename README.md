const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  LevelFormat, ExternalHyperlink
} = require('docx');
const fs = require('fs');

// Colors
const AMBER = "D97706";
const DARK  = "111827";
const GRAY  = "6B7280";
const GREEN = "059669";
const BLUE  = "2563EB";
const LIGHT_AMBER = "FEF3C7";
const LIGHT_GREEN = "D1FAE5";
const LIGHT_BLUE  = "DBEAFE";
const LIGHT_GRAY  = "F3F4F6";

const border = { style: BorderStyle.SINGLE, size: 1, color: "E5E7EB" };
const borders = { top: border, bottom: border, left: border, right: border };
const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text, bold: true, size: 36, color: DARK, font: "Arial" })],
    spacing: { before: 320, after: 160 },
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text, bold: true, size: 26, color: AMBER, font: "Arial" })],
    spacing: { before: 280, after: 120 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "FDE68A", space: 4 } },
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    children: [new TextRun({ text, bold: true, size: 22, color: DARK, font: "Arial" })],
    spacing: { before: 200, after: 80 },
  });
}

function body(text, opts = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: 20, color: opts.color || DARK, font: "Arial", bold: opts.bold || false, italics: opts.italic || false })],
    spacing: { before: 60, after: 60 },
  });
}

function mono(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: 18, font: "Courier New", color: "B45309" })],
    spacing: { before: 40, after: 40 },
    indent: { left: 360 },
  });
}

function bullet(text, indent = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level: indent },
    children: [new TextRun({ text, size: 20, color: DARK, font: "Arial" })],
    spacing: { before: 40, after: 40 },
  });
}

function bullet2(label, value) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children: [
      new TextRun({ text: label + ": ", bold: true, size: 20, color: DARK, font: "Arial" }),
      new TextRun({ text: value, size: 20, color: GRAY, font: "Arial" }),
    ],
    spacing: { before: 40, after: 40 },
  });
}

function infoBox(label, value, fillColor) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [
      new TableRow({
        children: [
          new TableCell({
            borders,
            width: { size: 9360, type: WidthType.DXA },
            shading: { fill: fillColor || LIGHT_AMBER, type: ShadingType.CLEAR },
            margins: { top: 120, bottom: 120, left: 180, right: 180 },
            children: [
              new Paragraph({
                children: [
                  new TextRun({ text: label + "  ", bold: true, size: 20, color: DARK, font: "Arial" }),
                  new TextRun({ text: value, size: 20, color: GRAY, font: "Arial" }),
                ],
              }),
            ],
          }),
        ],
      }),
    ],
  });
}

function codeBlock(lines) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [
      new TableRow({
        children: [
          new TableCell({
            borders,
            width: { size: 9360, type: WidthType.DXA },
            shading: { fill: "1F2937", type: ShadingType.CLEAR },
            margins: { top: 120, bottom: 120, left: 200, right: 200 },
            children: lines.map(l =>
              new Paragraph({
                children: [new TextRun({ text: l, size: 18, font: "Courier New", color: "D1FAE5" })],
                spacing: { before: 20, after: 20 },
              })
            ),
          }),
        ],
      }),
    ],
  });
}

function credTable(rows) {
  const headerRow = new TableRow({
    children: ["Employee", "Username", "Password (default)"].map(h =>
      new TableCell({
        borders,
        width: { size: 3120, type: WidthType.DXA },
        shading: { fill: AMBER, type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({ children: [new TextRun({ text: h, bold: true, size: 18, color: "FFFFFF", font: "Arial" })] })],
      })
    ),
  });
  const dataRows = rows.map(([a, b, c]) =>
    new TableRow({
      children: [a, b, c].map((val, i) =>
        new TableCell({
          borders,
          width: { size: 3120, type: WidthType.DXA },
          shading: { fill: i % 2 === 0 ? LIGHT_GRAY : "FFFFFF", type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: val, size: 18, font: i === 2 ? "Courier New" : "Arial", color: i === 2 ? "B45309" : DARK })] })],
        })
      ),
    })
  );
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [3120, 3120, 3120],
    rows: [headerRow, ...dataRows],
  });
}

function apiTable(rows) {
  const colWidths = [1200, 3200, 4960];
  const headerRow = new TableRow({
    children: ["Method", "Endpoint", "Description"].map((h, i) =>
      new TableCell({
        borders,
        width: { size: colWidths[i], type: WidthType.DXA },
        shading: { fill: "1F2937", type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({ children: [new TextRun({ text: h, bold: true, size: 17, color: "FFFFFF", font: "Arial" })] })],
      })
    ),
  });
  const methodColor = { GET: LIGHT_GREEN, POST: LIGHT_BLUE, PATCH: "FEE2E2", DELETE: "FEE2E2" };
  const methodText  = { GET: "059669", POST: "1D4ED8", PATCH: "DC2626", DELETE: "DC2626" };
  const dataRows = rows.map(([method, endpoint, desc]) =>
    new TableRow({
      children: [
        new TableCell({
          borders,
          width: { size: colWidths[0], type: WidthType.DXA },
          shading: { fill: methodColor[method] || LIGHT_GRAY, type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: method, bold: true, size: 16, font: "Courier New", color: methodText[method] || DARK })] })],
        }),
        new TableCell({
          borders,
          width: { size: colWidths[1], type: WidthType.DXA },
          shading: { fill: LIGHT_GRAY, type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: endpoint, size: 16, font: "Courier New", color: "7C3AED" })] })],
        }),
        new TableCell({
          borders,
          width: { size: colWidths[2], type: WidthType.DXA },
          shading: { fill: "FFFFFF", type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: desc, size: 17, font: "Arial", color: DARK })] })],
        }),
      ],
    })
  );
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [headerRow, ...dataRows],
  });
}

function spacer(pts = 200) {
  return new Paragraph({ children: [], spacing: { before: pts, after: 0 } });
}

// ─────────────────────────────────────
// Document
// ─────────────────────────────────────
const doc = new Document({
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [
          { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
          { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 360 } } } },
        ],
      },
    ],
  },
  styles: {
    default: { document: { run: { font: "Arial", size: 20 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: DARK },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: AMBER },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: "Arial", color: DARK },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 } },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    children: [

      // ── TITLE ──
      new Paragraph({
        children: [new TextRun({ text: "Neurax AI", bold: true, size: 56, color: AMBER, font: "Arial" })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 80 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "Project Management Agent", size: 30, color: GRAY, font: "Arial" })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 40 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "Full-Stack AI System · FastAPI + React + Groq LLM + SQLite", size: 20, color: GRAY, font: "Arial", italics: true })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 40 },
      }),
      new Paragraph({
        border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: AMBER, space: 4 } },
        children: [],
        spacing: { before: 120, after: 240 },
      }),

      // ── OVERVIEW ──
      h2("Overview"),
      body("Neurax is an autonomous AI-powered project management platform. It takes a project brief, decomposes it into tasks, assigns the right employees, recommends tools, analyses deadline feasibility, and flags risks — all powered by the Groq LLM."),
      spacer(120),

      // Feature highlights table
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [4680, 4680],
        rows: [
          new TableRow({
            children: [
              new TableCell({
                borders,
                width: { size: 4680, type: WidthType.DXA },
                shading: { fill: LIGHT_AMBER, type: ShadingType.CLEAR },
                margins: { top: 120, bottom: 120, left: 180, right: 180 },
                children: [
                  new Paragraph({ children: [new TextRun({ text: "Backend", bold: true, size: 20, color: AMBER, font: "Arial" })], spacing: { after: 80 } }),
                  ...[
                    "FastAPI + SQLite (WAL mode)",
                    "Groq LLM (llama3-70b-8192)",
                    "SHA-256 employee auth",
                    "PDF report generation (ReportLab)",
                    "Full REST API with Swagger UI",
                  ].map(t => bullet(t)),
                ],
              }),
              new TableCell({
                borders,
                width: { size: 4680, type: WidthType.DXA },
                shading: { fill: LIGHT_BLUE, type: ShadingType.CLEAR },
                margins: { top: 120, bottom: 120, left: 180, right: 180 },
                children: [
                  new Paragraph({ children: [new TextRun({ text: "Frontend", bold: true, size: 20, color: BLUE, font: "Arial" })], spacing: { after: 80 } }),
                  ...[
                    "React (Vite) + Axios",
                    "11-page dashboard (no router)",
                    "Employee login portal",
                    "Task progress tracking",
                    "Gantt chart, Analytics, Chat advisor",
                  ].map(t => bullet(t)),
                ],
              }),
            ],
          }),
        ],
      }),
      spacer(200),

      // ── PROJECT STRUCTURE ──
      h2("Project Structure"),
      codeBlock([
        "neurax/",
        "├── backend/",
        "│   ├── main.py                   ← FastAPI app (all endpoints)",
        "│   ├── agents/",
        "│   │   └── workflow.py           ← AI pipeline orchestrator",
        "│   ├── services/",
        "│   │   ├── groq_client.py        ← Groq LLM wrapper",
        "│   │   ├── task_decomposer.py",
        "│   │   ├── employee_matcher.py",
        "│   │   ├── overload_detector.py",
        "│   │   ├── skill_gap_detector.py",
        "│   │   ├── tool_recommender.py",
        "│   │   └── deadline_analyzer.py",
        "│   ├── datasets/",
        "│   │   ├── neurax_employees_dataset.csv",
        "│   │   ├── neurax_tools_dataset.csv",
        "│   │   ├── neurax_project_history_dataset.csv",
        "│   │   ├── neurax_projects_dataset.csv",
        "│   │   └── neurax.db             ← SQLite (auto-created)",
        "│   ├── .env                      ← GROQ_API_KEY goes here",
        "│   └── requirements.txt",
        "└── frontend/",
        "    ├── src/",
        "    │   └── App.js                ← Single-file React app",
        "    ├── package.json",
        "    └── vite.config.js",
      ]),
      spacer(200),

      // ── QUICK START ──
      h2("Quick Start"),

      h3("Prerequisites"),
      bullet("Python 3.10+"),
      bullet("Node.js 18+"),
      bullet("A free Groq API key from console.groq.com"),
      spacer(120),

      h3("1. Clone & set up backend"),
      codeBlock([
        "git clone https://github.com/yourname/neurax.git",
        "cd neurax/backend",
        "pip install -r requirements.txt",
        "",
        "# Create .env file",
        'echo "GROQ_API_KEY=your_key_here" > .env',
        "",
        "# Start the server",
        "uvicorn main:app --reload --port 8000",
      ]),
      spacer(120),

      h3("2. Start frontend"),
      codeBlock([
        "cd neurax/frontend",
        "npm install",
        "npm run dev",
        "",
        "# App runs at http://localhost:5173",
      ]),
      spacer(120),

      h3("3. Verify"),
      codeBlock([
        "# Health check",
        "curl http://localhost:8000/health",
        "",
        "# Swagger UI",
        "http://localhost:8000/docs",
      ]),
      spacer(200),

      // ── ENVIRONMENT ──
      h2("Environment Variables"),
      body("Create a .env file inside the backend/ directory:"),
      spacer(80),
      codeBlock([
        "# backend/.env",
        "GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      ]),
      spacer(100),
      infoBox("Note:", "The server will refuse to start if GROQ_API_KEY is missing. Get a free key at console.groq.com", LIGHT_AMBER),
      spacer(200),

      // ── DATABASE ──
      h2("Database"),
      body("Neurax uses SQLite (datasets/neurax.db) with WAL mode for concurrent reads. The database is auto-created on first startup and seeded from the CSV files in datasets/."),
      spacer(120),

      h3("Tables"),
      ...[
        ["projects", "All projects with status tracking"],
        ["employees", "Employee profiles, skills, workload"],
        ["tools", "Recommended dev tools catalogue"],
        ["history", "Completed project records + scores"],
        ["analyses", "Cached AI analysis results (JSON)"],
        ["task_progress", "Per-employee task completion tracking"],
        ["users", "Employee login credentials (hashed)"],
      ].map(([table, desc]) => bullet2(table, desc)),
      spacer(200),

      // ── CREDENTIALS ──
      h2("Default Credentials"),
      body("Employee accounts are auto-created on first startup from the employees CSV. The default credentials follow a simple pattern:"),
      spacer(100),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [4680, 4680],
        rows: [
          new TableRow({
            children: [
              new TableCell({
                borders,
                width: { size: 4680, type: WidthType.DXA },
                shading: { fill: LIGHT_AMBER, type: ShadingType.CLEAR },
                margins: { top: 100, bottom: 100, left: 160, right: 160 },
                children: [
                  new Paragraph({ children: [new TextRun({ text: "Username", bold: true, size: 20, color: AMBER, font: "Arial" })] }),
                  new Paragraph({ children: [new TextRun({ text: "First name in lowercase", size: 20, font: "Arial", color: DARK })] }),
                  new Paragraph({ children: [new TextRun({ text: 'e.g.  "Alice Johnson"  →  alice', size: 18, font: "Courier New", color: "B45309" })] }),
                ],
              }),
              new TableCell({
                borders,
                width: { size: 4680, type: WidthType.DXA },
                shading: { fill: LIGHT_GREEN, type: ShadingType.CLEAR },
                margins: { top: 100, bottom: 100, left: 160, right: 160 },
                children: [
                  new Paragraph({ children: [new TextRun({ text: "Password", bold: true, size: 20, color: GREEN, font: "Arial" })] }),
                  new Paragraph({ children: [new TextRun({ text: "Employee ID in lowercase", size: 20, font: "Arial", color: DARK })] }),
                  new Paragraph({ children: [new TextRun({ text: 'e.g.  EMP001  →  emp001', size: 18, font: "Courier New", color: "065F46" })] }),
                ],
              }),
            ],
          }),
        ],
      }),
      spacer(120),
      body("To view all auto-generated credentials, call the admin endpoint while the server is running:"),
      spacer(80),
      codeBlock(["GET  http://localhost:8000/api/auth/credentials"]),
      spacer(100),
      body("To change a password:"),
      codeBlock([
        'PATCH  http://localhost:8000/api/auth/change-password',
        '',
        '{ "username": "alice", "old_password": "emp001", "new_password": "MyNewPass" }',
      ]),
      spacer(200),

      // ── API REFERENCE ──
      h2("API Reference"),

      h3("Projects"),
      apiTable([
        ["GET",   "/api/projects",                    "List all projects"],
        ["GET",   "/api/projects/{id}",               "Get single project"],
        ["PATCH", "/api/projects/{id}/status",        "Update project status"],
        ["POST",  "/api/analyze/{project_id}",        "Run AI analysis on existing project"],
        ["POST",  "/api/analyze/custom",              "Analyse & save a new custom project"],
      ]),
      spacer(160),

      h3("Employees & Auth"),
      apiTable([
        ["GET",   "/api/employees",                   "List all employees"],
        ["GET",   "/api/employees/{id}/scorecard",    "AI-generated employee scorecard"],
        ["POST",  "/api/auth/login",                  "Employee login (returns JWT-free session)"],
        ["PATCH", "/api/auth/change-password",        "Change employee password"],
        ["GET",   "/api/auth/credentials",            "Admin: list all usernames + default passwords"],
      ]),
      spacer(160),

      h3("Progress & Analysis"),
      apiTable([
        ["POST",  "/api/progress",                    "Save / update task progress"],
        ["GET",   "/api/progress/employee/{id}",      "All task progress for one employee"],
        ["GET",   "/api/progress/project/{id}",       "Per-task avg progress for a project"],
        ["GET",   "/api/progress/all-projects",       "Overall % for all projects with data"],
        ["GET",   "/api/cache",                       "All cached analysis results"],
        ["GET",   "/api/report/{project_id}",         "Download PDF analysis report"],
      ]),
      spacer(160),

      h3("Intelligence Features"),
      apiTable([
        ["POST",  "/api/collaboration-score",         "AI collaboration score for two employees"],
        ["POST",  "/api/simulate",                    "What-if: change deadline or team size"],
        ["POST",  "/api/chat/{project_id}",           "AI Risk Advisor chat (project-scoped)"],
        ["POST",  "/api/assistant",                   "Global AI assistant (full workspace context)"],
        ["GET",   "/api/notifications",               "Smart alerts from live project data"],
      ]),
      spacer(160),

      h3("Dashboard & Analytics"),
      apiTable([
        ["GET",   "/api/dashboard",                   "Home page stats + projects list"],
        ["GET",   "/api/analytics",                   "Pre-aggregated chart data (6 charts)"],
        ["GET",   "/api/history",                     "Completed projects with success scores"],
        ["GET",   "/api/tools",                       "Tools catalogue"],
        ["GET",   "/health",                          "Health check"],
      ]),
      spacer(200),

      // ── PAGES ──
      h2("Frontend Pages"),
      ...[
        ["Home", "Overview dashboard — cached analyses, team workload, recent projects"],
        ["Project Analyser", "Select any project and run the full AI pipeline"],
        ["Custom Project", "Submit a new project brief — saved to dataset automatically"],
        ["AI Risk Advisor", "Project-scoped chat powered by Groq LLM"],
        ["Timeline Simulator", "Drag sliders to see how deadline/team changes affect feasibility"],
        ["Analytics", "6 live charts — priority, feasibility, workload, skills, tools, scores"],
        ["Employee Dashboard", "Team cards with skills, workload bars, and task assignments"],
        ["Collaboration Score", "AI rates how well two employees would work together"],
        ["Notifications", "Smart alerts — infeasible deadlines, skill gaps, overload warnings"],
        ["Project History", "Completed projects with success scores and tool usage"],
      ].map(([page, desc]) => bullet2(page, desc)),
      spacer(200),

      // ── REQUIREMENTS ──
      h2("Requirements"),

      h3("Backend (requirements.txt)"),
      codeBlock([
        "fastapi",
        "uvicorn[standard]",
        "python-dotenv",
        "pandas",
        "groq",
        "pydantic",
        "reportlab          # optional — PDF reports",
      ]),
      spacer(120),

      h3("Frontend (package.json)"),
      codeBlock([
        "react",
        "react-dom",
        "axios",
        "vite",
        "@vitejs/plugin-react",
      ]),
      spacer(200),

      // ── TROUBLESHOOTING ──
      h2("Troubleshooting"),
      ...[
        ["Server won't start", "Check that GROQ_API_KEY is set in backend/.env"],
        ["CORS errors", "Confirm the frontend runs on port 3000 or 5173 (both are whitelisted)"],
        ["Login fails", "Call GET /api/auth/credentials to see all valid usernames"],
        ["No analyses showing", "Run an analysis on the Project Analyser page first"],
        ["PDF download is a .txt", "Install ReportLab:  pip install reportlab --break-system-packages"],
        ["SQLite locked", "The database uses WAL mode — restart the server if issues persist"],
      ].map(([prob, fix]) => bullet2(prob, fix)),
      spacer(200),

      // ── FOOTER ──
      new Paragraph({
        border: { top: { style: BorderStyle.SINGLE, size: 4, color: "E5E7EB", space: 4 } },
        children: [
          new TextRun({ text: "Neurax AI  ·  Powered by Groq LLM  ·  v4.1.0", size: 16, color: GRAY, font: "Arial" }),
        ],
        alignment: AlignmentType.CENTER,
        spacing: { before: 200, after: 0 },
      }),
    ],
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync('/mnt/user-data/outputs/README.docx', buffer);
  console.log('Done: README.docx');
});
