"""Read an owned logger's identified CPU sensor; never changes hardware settings.

These conservative task thresholds are below the7840HS100C Tjmax. They are
not a diagnosis, a board-temperature measurement or a hardware safety limit.
"""
from datetime import datetime
from pathlib import Path
import math,time
import psutil
from meeting_acoustic_contract_20261116 import read,require,sha
from durable_model_state_20261117 import read_snapshot

class CpuThermalLimit(RuntimeError):
    def __init__(self,message,observation):
        super().__init__(message);self.observation=observation

def inspect_thermal_policy(policy):
    require(policy['sensorIdentifier']=='/amdcpu/0/temperature/2','Use the identified laptop CPU sensor')
    require(policy['maximumStartCelsius']==85 and policy['stopCelsius']==95,
        'Fixed conservative task thresholds changed')
    require(policy['maximumSampleAgeSeconds']==15 and policy['cacheSeconds']==1,
        'Fixed temperature freshness changed')
    require(policy['scope']=='owned model worker only; no system power/fan/clock changes',
        'Thermal guard scope changed')

def evaluate_temperature(snapshot,policy,*,now=None,starting=False):
    inspect_thermal_policy(policy)
    latest=snapshot['latest'];at=datetime.fromisoformat(latest['At'])
    current=now or datetime.now().astimezone();age=(current-at).total_seconds()
    require(-2<=age<=policy['maximumSampleAgeSeconds'],'Identified CPU temperature sample is stale or future-dated')
    values=[s for s in latest['CpuSensors'] if s['Identifier']==policy['sensorIdentifier']]
    require(len(values)==1 and '7840HS' in values[0]['Hardware'],'Identified CPU temperature missing or ambiguous')
    value=values[0]['Celsius']
    require(type(value) in (int,float) and math.isfinite(value) and 0<value<130,
        'Invalid identified CPU temperature')
    observed={'sampleAt':latest['At'],'celsius':value,'sampleAgeSeconds':age,
        'sensorIdentifier':values[0]['Identifier'],'taskStartThresholdCelsius':85,'taskStopThresholdCelsius':95,
        'hardwareOverheatCauseProven':False,'physicalMainboardTemperatureMeasured':False}
    if value>=policy['stopCelsius']:raise CpuThermalLimit('CPU temperature reached task stop threshold95C',observed)
    if starting and value>policy['maximumStartCelsius']:
        raise CpuThermalLimit('CPU temperature above task startup threshold85C',observed)
    return observed

class ThermalGuard:
    def __init__(self,policy):
        inspect_thermal_policy(policy);self.policy=policy;self.last=0.;self.observed=None
        for entry in policy['loggerSources']:
            require(sha(entry['file'])==entry['sha256'],'Frozen laptop logger source changed')
    def check(self,*,starting=False):
        tick=time.monotonic()
        if not starting and self.observed is not None and tick-self.last<self.policy['cacheSeconds']:
            return self.observed
        root=Path(self.policy['run']);started=read(root/'started.json')
        require(started['state']=='READ_ONLY_LAPTOP_THERMAL_MONITOR_RUNNING'
            and started['externalGpuQueried'] is False,'Wrong temperature logger profile')
        try:
            process=psutil.Process(started['pid'])
            require(abs(process.create_time()-started['createdAt'])<.01 and process.is_running(),
                'Temperature logger process identity changed')
        except psutil.Error as error:raise RuntimeError('Identified CPU temperature logger is not live') from error
        require(not(root/'completed.json').exists(),'Temperature logger is terminal')
        snapshot,selection=read_snapshot(root/'latest.json')
        observed=evaluate_temperature(snapshot,self.policy,starting=starting)
        observed['snapshotSelection']=selection;self.last=tick;self.observed=observed
        return observed
