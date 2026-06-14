from pathlib import Path
import yaml

def discover_workflows():
    workflow_root= Path(__file__).parent.parent / "workflows"
    workflows=[]
    for workflows_dir in workflow_root.iterdir():
        if workflows_dir.is_dir():
            yaml_file=workflows_dir/ "workflow.yaml"
            if yaml_file.is_file():
                workflows.append(workflows_dir.name)
    return workflows


def discover_workflow_path():
    workflow_root= Path(__file__).parent.parent / "workflows"
    workflows=[]
    for workflows_dir in workflow_root.iterdir():
        if workflows_dir.is_dir():
            yaml_file=workflows_dir/ "workflow.yaml"
            if yaml_file.is_file():
                workflows.append(yaml_file)
    return workflows
    

def read_workflow(workflow_path: Path):
    with open(workflow_path,"r") as f:
        return yaml.safe_load(f)