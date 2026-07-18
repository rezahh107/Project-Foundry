#!/usr/bin/env python3
"""Deterministic cross-file validation for the Project Foundry foundation."""
from __future__ import annotations
import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALLOWED_TASK_STATES={"planned","eligible","active","implementation_submitted","validation_pending","validated_on_branch","merge_pending","merged","current_main_verified","complete","blocked","invalidated","superseded"}
REQUIRED_FILES=["README.md","PROJECT_CHARTER.md","SYSTEM_MAP.md","AGENTS.md","governance/project-constitution.v1.json","planning/execution-program.v1.json","planning/scope-baseline.v1.json","planning/current-state.v1.json","planning/NEXT_WORK.md","decisions/decision-registry.v1.json","dogfooding/dogfooding-registry.v1.json"]

@dataclass(frozen=True)
class ValidationIssue:
    code:str
    message:str

def load_json(root:Path,relative:str)->dict[str,Any]:
    return json.loads((root/relative).read_text(encoding="utf-8"))

def duplicates(values:list[str])->set[str]:
    seen:set[str]=set(); found:set[str]=set()
    for value in values:
        if value in seen: found.add(value)
        seen.add(value)
    return found

def validate(root:Path)->list[ValidationIssue]:
    issues:list[ValidationIssue]=[]
    for relative in REQUIRED_FILES:
        if not (root/relative).is_file(): issues.append(ValidationIssue("PFV-001",f"required file missing: {relative}"))
    if issues: return issues
    try:
        constitution=load_json(root,"governance/project-constitution.v1.json")
        program=load_json(root,"planning/execution-program.v1.json")
        scope=load_json(root,"planning/scope-baseline.v1.json")
        state=load_json(root,"planning/current-state.v1.json")
        decisions=load_json(root,"decisions/decision-registry.v1.json")
        dogfooding=load_json(root,"dogfooding/dogfooding-registry.v1.json")
    except (OSError,json.JSONDecodeError) as exc:
        return [ValidationIssue("PFV-002",f"canonical JSON cannot be read: {exc}")]
    documents=[constitution,program,scope,state,decisions,dogfooding]
    project_ids={doc.get("project_id") for doc in documents}
    if project_ids!={"PROJECT-FOUNDRY"}: issues.append(ValidationIssue("PFV-010",f"project identity mismatch: {sorted(map(str,project_ids))}"))
    north_star_id=constitution.get("north_star",{}).get("id")
    if north_star_id!="PF-NORTH-STAR-001": issues.append(ValidationIssue("PFV-011","canonical North Star identity changed or missing"))
    for name,doc in [("program",program),("scope",scope),("state",state),("decisions",decisions),("dogfooding",dogfooding)]:
        if doc.get("north_star_id")!=north_star_id: issues.append(ValidationIssue("PFV-012",f"{name} is not bound to canonical North Star"))
    work_packages=program.get("work_packages",[]); tasks=program.get("tasks",[])
    wp_ids=[item.get("id") for item in work_packages]; task_ids=[item.get("id") for item in tasks]
    if duplicates([str(x) for x in wp_ids]): issues.append(ValidationIssue("PFV-020","duplicate work package IDs"))
    if duplicates([str(x) for x in task_ids]): issues.append(ValidationIssue("PFV-021","duplicate task IDs"))
    wp_map={item.get("id"):item for item in work_packages}; task_map={item.get("id"):item for item in tasks}
    for task in tasks:
        task_id=task.get("id")
        if task.get("work_package_id") not in wp_map: issues.append(ValidationIssue("PFV-022",f"task {task_id} references unknown work package"))
        if task.get("status") not in ALLOWED_TASK_STATES: issues.append(ValidationIssue("PFV-023",f"task {task_id} has invalid status {task.get('status')}"))
        for dep in task.get("depends_on",[]):
            if dep not in task_map: issues.append(ValidationIssue("PFV-024",f"task {task_id} references unknown dependency {dep}"))
            if dep==task_id: issues.append(ValidationIssue("PFV-025",f"task {task_id} depends on itself"))
        if not task.get("acceptance_criteria"): issues.append(ValidationIssue("PFV-026",f"task {task_id} has no acceptance criteria"))
        if task.get("status") in {"complete","current_main_verified"} and not task.get("evidence_refs"): issues.append(ValidationIssue("PFV-027",f"task {task_id} claims completion without evidence"))
        if task.get("status")=="complete": issues.append(ValidationIssue("PFV-028",f"task {task_id} must preserve current_main_verified evidence state"))
    for wp in work_packages:
        for task_id in wp.get("task_ids",[]):
            if task_id not in task_map: issues.append(ValidationIssue("PFV-029",f"work package {wp.get('id')} references unknown task {task_id}"))
            elif task_map[task_id].get("work_package_id")!=wp.get("id"): issues.append(ValidationIssue("PFV-030",f"task {task_id} work package linkage is inconsistent"))
    included_wps=set(scope.get("included_work_package_ids",[])); included_tasks=set(scope.get("included_task_ids",[]))
    if not included_wps.issubset(wp_map): issues.append(ValidationIssue("PFV-040","scope includes unknown work package"))
    if not included_tasks.issubset(task_map): issues.append(ValidationIssue("PFV-041","scope includes unknown task"))
    if scope.get("active_task_id") not in included_tasks: issues.append(ValidationIssue("PFV-042","active task is outside active scope"))
    if scope.get("silent_scope_change_allowed") is not False: issues.append(ValidationIssue("PFV-043","silent scope changes must be disabled"))
    current_task_id=state.get("current_task_id")
    if current_task_id!=scope.get("active_task_id"): issues.append(ValidationIssue("PFV-050","current state and scope baseline disagree on active task"))
    if current_task_id not in included_tasks: issues.append(ValidationIssue("PFV-051","current task is outside included scope"))
    if state.get("current_task_status")!=task_map.get(current_task_id,{}).get("status"): issues.append(ValidationIssue("PFV-052","current task status differs from execution program"))
    expected_context=[north_star_id,program.get("program_id"),task_map.get(current_task_id,{}).get("work_package_id"),current_task_id]
    if state.get("active_context_path")!=expected_context: issues.append(ValidationIssue("PFV-053",f"active context path must be {expected_context}"))
    if state.get("program_ref")!=f"{program.get('program_id')}@{program.get('program_version')}": issues.append(ValidationIssue("PFV-054","current state has stale program reference"))
    if state.get("scope_ref")!=f"{scope.get('scope_id')}@{scope.get('scope_version')}": issues.append(ValidationIssue("PFV-055","current state has stale scope reference"))
    for completed_id in state.get("completed_task_ids",[]):
        completed=task_map.get(completed_id)
        if not completed: issues.append(ValidationIssue("PFV-056",f"unknown completed task {completed_id}"))
        elif completed.get("status")!="current_main_verified" or not completed.get("evidence_refs"): issues.append(ValidationIssue("PFV-057",f"completed task {completed_id} lacks exact-main status or evidence"))
    if state.get("next_task_id") not in task_map: issues.append(ValidationIssue("PFV-058","next task does not exist"))
    decision_ids=[item.get("id") for item in decisions.get("decisions",[])]
    if duplicates([str(x) for x in decision_ids]): issues.append(ValidationIssue("PFV-060","duplicate decision IDs"))
    for decision in decisions.get("decisions",[]):
        decision_id=decision.get("id"); decision_class=decision.get("decision_class")
        if decision_class not in {"D1_LIGHTWEIGHT","D2_STRUCTURED","D3_HIGH_CONSEQUENCE"}: issues.append(ValidationIssue("PFV-061",f"decision {decision_id} has invalid class"))
        if decision_class in {"D2_STRUCTURED","D3_HIGH_CONSEQUENCE"}:
            weights=decision.get("criteria_weights",{})
            if sum(weights.values())!=100: issues.append(ValidationIssue("PFV-062",f"decision {decision_id} criteria weights must total 100"))
            for required in ["ai_operability","owner_usability"]:
                if required not in weights: issues.append(ValidationIssue("PFV-063",f"decision {decision_id} is missing criterion {required}"))
            if not decision.get("hard_constraints"): issues.append(ValidationIssue("PFV-064",f"decision {decision_id} has no hard constraints"))
        if decision.get("status")=="research_required" and decision.get("selected_option") is not None: issues.append(ValidationIssue("PFV-065",f"decision {decision_id} selected an option before research"))
    observation_ids={item.get("id") for item in dogfooding.get("observations",[])}; lesson_ids={item.get("id") for item in dogfooding.get("lesson_candidates",[])}
    for lesson in dogfooding.get("lesson_candidates",[]):
        for ref in lesson.get("observation_refs",[]):
            if ref not in observation_ids: issues.append(ValidationIssue("PFV-070",f"lesson {lesson.get('id')} references unknown observation {ref}"))
    for promotion in dogfooding.get("promotions",[]):
        if promotion.get("lesson_id") not in lesson_ids: issues.append(ValidationIssue("PFV-071",f"promotion {promotion.get('id')} references unknown lesson"))
        if not promotion.get("authority") or not promotion.get("evidence_refs") or not promotion.get("carrier_refs"): issues.append(ValidationIssue("PFV-072",f"promotion {promotion.get('id')} is missing authority, evidence, or carrier"))
        if promotion.get("status")=="automatic": issues.append(ValidationIssue("PFV-073","dogfooding promotion may not be automatic"))
    if constitution.get("operating_profile",{}).get("security_priority")!="low_with_mandatory_safety_floor": issues.append(ValidationIssue("PFV-080","security profile must preserve mandatory safety floor"))
    completion_rule=constitution.get("completion_rule",{})
    if completion_rule.get("required_lifecycle_state")!="current_main_verified" or completion_rule.get("evidence_required") is not True: issues.append(ValidationIssue("PFV-081","completion rule is weaker than required"))
    next_work=(root/"planning/NEXT_WORK.md").read_text(encoding="utf-8")
    for required_text in [north_star_id,program.get("program_id"),current_task_id]:
        if required_text not in next_work: issues.append(ValidationIssue("PFV-090",f"NEXT_WORK omits required context landmark {required_text}"))
    return issues

def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--root",default="."); args=parser.parse_args(); issues=validate(Path(args.root).resolve())
    if issues:
        for issue in issues: print(f"{issue.code}: {issue.message}",file=sys.stderr)
        print(f"Validation failed with {len(issues)} issue(s).",file=sys.stderr); return 1
    print("Project Foundry foundation validation: PASS"); return 0

if __name__=="__main__": raise SystemExit(main())
