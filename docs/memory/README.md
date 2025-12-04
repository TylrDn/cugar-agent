# Memory for CUGA

This document explains how to enable the use of the memory feature in CUGA.

## 🎯 Overview

CUGA execution can be enhanced by enabling episodic memory, which introduces the ability to levearge previously identified insights and relevant experiences when generating the final answer.
Some key features include:

### 1. Agentic Memory Component

- Extract and store tips in Milvus via mem0 interface.
- Endpoints to support CRUD operations for tips and namespaces.
- Memory Client for communication with endpoints.
- Database dependencies:
  - Milvus (for tips)
  - SQLite (for namespace lookup)

### 2. Integration with cuga-agent

- Adds `enable_memory` flag to control memory features.
- Support Memory port configuration in `settings.toml`
- Uses retrieved memory in agents:
  - Task analyzer
  - Task decomposition
  - API shortlist
  - Code agent
  - API Code Planner
    (Will expand to other agents with more experiments)
 - Extracts tips at the end of a run in activity tracker:
		self.memory.end_run(namespace_id="memory", run_id=self.experiment_folder)



## 🚀  Quick Start

1. Set `enable_memory=true` in `settings.toml`
2. Start memory API:
	`cuga start memory`
The API will be available at port 8888.



## 📁 Prompt Location
```
cuga/
└── backend/memory/agentic_memory/llm/tips/     
           		                        └── prompts		# Folder with all prompts       	
```            
            
## 🔧 How It Works
The use cases which motivate the need for memory for CUGA include:
1. Generate insights from successful/failed trajectories 
- During execution,  `memory.add_step` captures  summary of step output and any relevant information
- The Activity Tracker activates `memory.end_run` at the final step of the FinalAnswerAgent execution
- A background process is triggered, to `analyze_run` of the stored trajectory
- Analysis invokes LLM with prompt tailored to  `extract_cuga_tips_from_data`, resulting in identification, extraction and classification of tips per Cuga sub-agent
- `create_and_store_fact `is invoked for each tip, along with relevant metadata  
