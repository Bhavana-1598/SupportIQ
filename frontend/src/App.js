
import React, { useState } from "react";
import axios from "axios";

function App(){

const [title,setTitle]=useState("");
const [description,setDescription]=useState("");
const [tech,setTech]=useState("");
const [tools,setTools]=useState("");
const [deadline,setDeadline]=useState("");
const [result,setResult]=useState(null);

const submitProject = async () => {

const res = await axios.post("http://localhost:8000/analyze_project",{
title:title,
description:description,
technologies:tech,
tools:tools,
deadline_days:Number(deadline)
});

setResult(res.data);

}

return(
<div style={{padding:"40px"}}>

<h1>Autonomous Workflow AI Agent</h1>

<input placeholder="Project Title" onChange={(e)=>setTitle(e.target.value)} />
<br/>
<input placeholder="Description" onChange={(e)=>setDescription(e.target.value)} />
<br/>
<input placeholder="Technologies" onChange={(e)=>setTech(e.target.value)} />
<br/>
<input placeholder="Tools" onChange={(e)=>setTools(e.target.value)} />
<br/>
<input placeholder="Deadline days" onChange={(e)=>setDeadline(e.target.value)} />
<br/>
<button onClick={submitProject}>Analyze Project</button>

{result && (
<div>

<h2>Tasks</h2>
<pre>{JSON.stringify(result.tasks,null,2)}</pre>

<h2>Assignments</h2>
<pre>{JSON.stringify(result.assignments,null,2)}</pre>

<h2>Skill Gap</h2>
<pre>{JSON.stringify(result.skill_gap,null,2)}</pre>

<h2>Recommended Tools</h2>
<pre>{JSON.stringify(result.recommended_tools,null,2)}</pre>

<h2>Deadline Report</h2>
<pre>{JSON.stringify(result.deadline_report,null,2)}</pre>

</div>
)}

</div>
)
}

export default App;
