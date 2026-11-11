"""Delivery continuation regressions: no cloud, devices or product execution."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from resume_delivery import current,active_execution,CORE

class DeliveryContinuationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.config={"steps":[{"id":"save","receipt":"saved.json","equals":{"source":"frozen","state":"PASSED"},"command":["must-not-run.py"]}],"afterDelivery":"next original item"}
 def write(self,name,data):
  (self.root/name).write_text(json.dumps(data),encoding="utf-8")
 def state(self,query=None):
  return current(self.root,self.config,query or (lambda handle:self.fail("Unexpected job query")))
 def job(self):
  self.write("freeze.json",{"sourceCommit":"frozen","run":17})
  self.config["steps"][0]["job"]={"freeze":"freeze.json","runField":"run","prepare":"freeze existing work"}
 def test_missing_receipt_requires_work_even_if_old_metadata_claims_qualified(self):
  self.config["qualified"]=True
  self.assertEqual(self.state()["kind"],"READY")
 def test_existing_wrong_source_stops_before_any_reexecution(self):
  self.write("saved.json",{"source":"older","state":"PASSED"})
  result=self.state();self.assertEqual(result["kind"],"FAILED");self.assertNotIn("command",result)
 def test_matching_receipt_is_reused_without_running_its_command(self):
  self.write("saved.json",{"source":"frozen","state":"PASSED"})
  result=self.state();self.assertEqual(result["kind"],"BATCH_DELIVERED");self.assertFalse(result["wholeGoalComplete"])
 def test_tampered_binary_invalidates_a_previously_passed_receipt(self):
  file=self.root/"own.bin";file.write_bytes(b"original")
  self.write("saved.json",{"source":"frozen","state":"PASSED","file":str(file),"sha":hashlib.sha256(b"original").hexdigest()})
  self.config["steps"][0]["binary"]={"pathField":"file","shaField":"sha"}
  self.assertEqual(self.state()["kind"],"BATCH_DELIVERED")
  file.write_bytes(b"changed");self.assertEqual(self.state()["kind"],"FAILED")
 def test_live_exact_job_is_a_verified_wait_not_a_restart_instruction(self):
  self.job();seen=[]
  result=self.state(lambda handle:seen.append(handle) or {"head_sha":"frozen","status":"in_progress","conclusion":None})
  self.assertEqual(seen,[17]);self.assertEqual(result["kind"],"VERIFIED_WAIT");self.assertNotIn("command",result)
 def test_successful_other_source_does_not_qualify_the_pending_source(self):
  self.job()
  self.assertEqual(self.state(lambda handle:{"head_sha":"other","status":"completed","conclusion":"success"})["kind"],"FAILED")
 def test_failed_run_remains_failed_even_if_a_receipt_is_present(self):
  self.job();self.write("saved.json",{"source":"frozen","state":"PASSED"})
  self.assertEqual(self.state(lambda handle:{"head_sha":"frozen","status":"completed","conclusion":"failure"})["kind"],"FAILED")
 def test_missing_runtime_handle_returns_engineering_action_without_dispatch(self):
  self.job();self.write("freeze.json",{"sourceCommit":"frozen"})
  self.assertEqual(self.state()["kind"],"ENGINEERING_ACTION")
 def test_original_next_change_does_not_resume_the_previous_delivered_batch(self):
  root={};node=root
  for key in CORE:node[key]={};node=node[key]
  node.update(next=CORE[-1]+".visual",old={"deliveryExecution":self.config},visual={"state":"SOURCE","next":"finish the whole page"})
  config,work=active_execution(root)
  self.assertIsNone(config);self.assertEqual(work["next"],"finish the whole page")
 def test_actual_phone_or_customer_stage_without_a_command_requires_engineering(self):
  self.config["steps"][0].pop("command");self.config["steps"][0]["prepare"]="Use the prepared ordinary public entry"
  result=self.state();self.assertEqual(result["kind"],"ENGINEERING_ACTION");self.assertNotIn("command",result)
 def test_same_product_receipt_from_an_old_verifier_is_not_reused(self):
  self.job();step=self.config["steps"][0];step["boundToFreezeSource"]="testSourceCommit"
  self.write("saved.json",{"source":"frozen","state":"PASSED","testSourceCommit":"older-verifier"})
  query=lambda handle:{"head_sha":"frozen","status":"completed","conclusion":"success"}
  self.assertEqual(self.state(query)["kind"],"FAILED")
  self.write("saved.json",{"source":"frozen","state":"PASSED","testSourceCommit":"frozen"})
  self.assertEqual(self.state(query)["kind"],"BATCH_DELIVERED")
if __name__=="__main__":unittest.main()
