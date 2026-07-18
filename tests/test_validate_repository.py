from __future__ import annotations
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from scripts.validate_repository import validate

REPO_ROOT=Path(__file__).resolve().parents[1]

class RepositoryValidationTests(unittest.TestCase):
    def test_repository_foundation_is_valid(self)->None:
        self.assertEqual([],validate(REPO_ROOT))
    def test_forgotten_north_star_is_rejected(self)->None:
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"repo"; shutil.copytree(REPO_ROOT,target)
            path=target/"planning/current-state.v1.json"; data=json.loads(path.read_text(encoding="utf-8"))
            data["north_star_id"]="FORGOTTEN"; data["active_context_path"][0]="FORGOTTEN"
            path.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
            self.assertIn("PFV-012",{issue.code for issue in validate(target)})
    def test_completion_without_evidence_is_rejected(self)->None:
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"repo"; shutil.copytree(REPO_ROOT,target)
            path=target/"planning/execution-program.v1.json"; data=json.loads(path.read_text(encoding="utf-8"))
            data["tasks"][0]["status"]="current_main_verified"; data["tasks"][0]["evidence_refs"]=[]
            path.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
            self.assertIn("PFV-027",{issue.code for issue in validate(target)})
    def test_major_decision_requires_ai_operability(self)->None:
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"repo"; shutil.copytree(REPO_ROOT,target)
            path=target/"decisions/decision-registry.v1.json"; data=json.loads(path.read_text(encoding="utf-8"))
            weights=data["decisions"][0]["criteria_weights"]; weights["technical_fitness"]+=weights.pop("ai_operability")
            path.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
            self.assertIn("PFV-063",{issue.code for issue in validate(target)})

if __name__=="__main__": unittest.main()
