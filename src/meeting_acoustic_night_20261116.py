"""Inspect or explicitly run the one fixed night batch; no scheduler/retries."""
from pathlib import Path
from datetime import datetime
import argparse
import json
import subprocess
from meeting_acoustic_contract_20261116 import read, require, sha, verify_bindings
from meeting_acoustic_worker_20261116 import own_limits, present_discrete_gpu


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--packet',type=Path,required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--inspect',action='store_true')
    mode.add_argument('--execute-night',action='store_true')
    parser.add_argument('--resume-training',action='store_true')
    parser.add_argument('--resume-evaluation',action='store_true')
    args = parser.parse_args(); packet = read(args.packet); verify_bindings(packet)
    limits = own_limits(5 if args.inspect else 25)
    root = Path(packet['runRoot']); python = packet['runtime']['python']
    preflight = [python,packet['trainingWorker'],'--packet',str(args.packet),
                 '--mode','preflight','--run',str(root/'gpu-preflight')]
    training = [python,packet['trainingWorker'],'--packet',str(args.packet),
                '--mode','train','--run',str(root/'training')]
    evaluation = [python,packet['evaluationWorker'],'--packet',str(args.packet),
                  '--training-run',str(root/'training'),'--run',str(root/'evaluation')]
    scoring = [packet['scoringPython'],packet['independentScorer'],
               '--control',packet['scoringControl'],'--run',str(root/'evaluation'),
               '--output',str(root/'raw-score.json')]
    if args.inspect:
        print(json.dumps({'state':'NIGHT_COMMANDS_INSPECTED_NO_EXECUTION','phases':[preflight,training,evaluation,scoring],
                          'actualGpuPreflightPassed':False,'cpuOrIntegratedTrainingAllowed':False,
                          'newNeuralCalls':0,'scheduledJobCreated':False,'limits':limits.query()},ensure_ascii=False))
        return
    present_discrete_gpu()
    binding = {'packetSha256':sha(args.packet),'workerSha256':sha(packet['trainingWorker'])}
    root.mkdir(parents=True,exist_ok=True)
    def execute(name,command):
        with (root/(name+'-console.log')).open('a',encoding='utf-8') as log:
            log.write('\n'+datetime.now().astimezone().isoformat()+' '+json.dumps(command)+'\n'); log.flush()
            child = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        require(child.returncode == 0,name+' stopped; inspect its preserved state/console. No automatic retry.')
    proof = Path(packet['preflightReceipt'])
    if not proof.exists():
        require(not (root/'gpu-preflight').exists(),'Existing failed preflight is retained; repair before retrying')
        execute('preflight',preflight)
    checked = read(proof)
    require(checked['state'] == 'PASS_ACTUAL_DISCRETE_GPU_ACOUSTIC_TRAINING_PREFLIGHT'
            and checked['binding'] == binding,'GPU preflight binding changed')
    if not (root/'training/training-complete.json').exists():
        if (root/'training').exists():
            require(args.resume_training,'Existing training run requires explicit resume after inspecting its stop reason')
            training.append('--resume')
        execute('training',training)
    if not (root/'evaluation/evaluation-complete.json').exists():
        if (root/'evaluation').exists():
            require(args.resume_evaluation,'Existing evaluation requires explicit resume; failed prefixes are never retried')
            evaluation.append('--resume')
        execute('evaluation',evaluation)
    if not (root/'raw-score.json').exists():
        execute('scoring',scoring)
    score = read(root/'raw-score.json')
    require(score['scoringControlSha256'] == sha(packet['scoringControl'])
            and score['evaluationStateSha256'] == sha(root/'evaluation/evaluation-complete.json'),
            'Completed score belongs to a different evaluation')
    print(json.dumps({'state':'NIGHT_RAW_PILOT_COMPLETE_PERSON_AND_PRODUCT_GATES_PENDING',
                      'score':str(root/'raw-score.json'),'qualityQualified':False,'saleQualified':False},ensure_ascii=False))


if __name__ == '__main__':
    main()
