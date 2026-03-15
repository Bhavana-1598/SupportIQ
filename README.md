# 🧠 SupportIQ AI Agent — Intelligent Project Management Agent

> **Autonomous AI-powered project management** · FastAPI + React + Groq LLM + SQLite

---

## 📌 What is SupportIQ?

Neurax is a full-stack AI agent designed to take the complexity out of project planning. You give it a project — a name, description, required skills, and a deadline — and it handles the rest autonomously.

Under the hood, Neurax uses **Groq's LLM (llama-3.3-70b-versatile)** to think through your project like an experienced project manager. It breaks the work into structured tasks, matches those tasks to the right employees based on skills and availability, predicts whether your deadline is realistic, spots overload and skill gaps before they become problems, and recommends the best tools for the job.

Everything is persisted in a lightweight **SQLite database**, served through a **FastAPI backend**, and presented in a clean **React dashboard** — no complex infrastructure, no cloud dependencies, just a focused tool that works.

Whether you are managing a team of engineers, planning an AI product, or just trying to figure out who should do what and by when — Neurax gives you an intelligent second opinion in seconds.

---

## ✨ Features

### 🤖 AI Project Analysis
Submit any project and the AI pipeline automatically decomposes it into phases and tasks, assigns employees based on skill match and workload, estimates timelines, and delivers a full structured plan — all in one click.

### 📋 Task Decomposition
The agent breaks your project into logical, phase-based tasks with estimated durations, required skills, and dependencies clearly mapped out. Every task is traceable from planning to delivery.

### 👥 Smart Employee Assignment
Neurax reads your employee dataset — skills, experience, current workload — and assigns the right people to the right tasks. It avoids overloading team members and flags when someone is being stretched too thin.

### ⚠️ Risk Analysis
Before you commit to a plan, Neurax surfaces the risks. It detects workload overload, skill gaps, and deadline infeasibility — and gives you concrete recommendations to address each one.

### 📅 Deadline Feasibility Engine
The system calculates whether your deadline is achievable given the task complexity and team capacity. It tells you if the plan is Feasible, Tight, At Risk, or Infeasible — along with the exact buffer or overrun in days.

### 📊 Gantt Chart
Every analysis generates a visual Gantt chart showing how tasks are distributed across the timeline, colour-coded by phase, so you can immediately see where the bottlenecks are.

### 🛠️ Tool Recommendations
Neurax recommends the most suitable development tools and platforms for your project based on the tech stack and project type — drawn from a curated tools dataset.

### 💬 AI Risk Advisor
A project-scoped chat interface powered by Groq LLM. Ask anything about your project — "Is the deadline realistic?", "Who is most at risk of burnout?", "What tasks can run in parallel?" — and get specific, data-grounded answers.


### 🤝 Collaboration Score
Pick any two employees and the AI rates their collaboration potential across four dimensions — skill complementarity, experience balance, workload compatibility, and role synergy — with a summary and best project types for the pair.

### 📈 Live Analytics
Six real-time charts covering priority distribution, deadline feasibility breakdown, team workload, top skills across the organisation, tool usage frequency, and historical success scores.

### 🔔 Smart Notifications
The system continuously scans your live project and employee data and surfaces contextual alerts — infeasible deadlines, tight buffers, skill gaps, overloaded employees, and underutilised team members — ranked by severity.

### 🏗️ Custom Project Submission
Add a brand-new project directly from the UI. Fill in the brief and the system runs the full AI pipeline, saves the project to the database, and makes it available in the Project Analyser — all in one action.

### 👤 Employee Portal
Employees can log in with their own credentials and see a personal dashboard — their assigned tasks across all projects, progress bars, and the ability to update task status and add notes.

### ✅ Task Progress Tracking
Employees update their task completion percentage and status (Not Started, In Progress, Completed, Blocked) directly from the dashboard. Progress rolls up into per-project completion views visible to everyone.

### 📄 PDF Report Generation
Every analysed project can be exported as a structured PDF report — covering task breakdown, assignments, risk analysis, and deadline summary — ready to share with stakeholders.

### 🏆 Project History
A searchable archive of completed projects with success scores, team sizes, tools used, and delivery timelines. Useful for benchmarking and retrospectives.

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| 🤖 LLM | Groq — llama-3.3-70b-versatile |
| ⚙️ Backend | FastAPI, Python 3.10+ |
| 🗄️ Database | SQLite (WAL mode) |
| 🎨 Frontend | React 18, Vite, Axios |
| 🔐 Auth | SHA-256 password hashing |
| 📄 PDF | ReportLab |

---


