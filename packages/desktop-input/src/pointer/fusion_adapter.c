/* Platform adapter only; Fusion's MIT AHRS/bias implementation is unchanged.
 * Desktop-only: this code is never linked into WBA firmware. */
#include "FusionAhrs.h"
#include "FusionBias.h"
#include <stdlib.h>
#include <math.h>
typedef struct {FusionAhrs ahrs;FusionBias bias;} CompanionFusion;
void companion_fusion_configure(void *handle,float sample_rate) {
    CompanionFusion *s=(CompanionFusion*)handle;
    FusionAhrsSettings a=fusionAhrsDefaultSettings;
    a.sampleRate=sample_rate;a.gyroscopeRange=250.0f;
    a.gain=0.5f;a.accelerationRejection=10.0f;a.rejectionTimeout=5.0f;
    FusionAhrsSetSettings(&s->ahrs,&a);
    FusionBiasSettings b=fusionBiasDefaultSettings;
    b.sampleRate=sample_rate;b.stationaryThreshold=0.5f;b.stationaryPeriod=1.0f;
    FusionBiasSetSettings(&s->bias,&b);
}
void *companion_fusion_create(void) {
    CompanionFusion *s=(CompanionFusion*)calloc(1,sizeof(CompanionFusion));
    if(!s)return NULL;
    FusionAhrsInitialise(&s->ahrs);FusionBiasInitialise(&s->bias);
    companion_fusion_configure(s,100.0f);return s;
}
void companion_fusion_destroy(void *handle){free(handle);}
void companion_fusion_align(void *handle,const float accel[3]) {
    CompanionFusion *s=(CompanionFusion*)handle;
    const FusionVector zero=FUSION_VECTOR_ZERO;
    const FusionVector a={.array={accel[0]*0.001f,accel[1]*0.001f,accel[2]*0.001f}};
    /* Initialise from the already measured stationary gravity. This runs the
     * upstream correction with ZERO angular motion; it is not fabricated
     * sensor data or an extra integration of the user's movement. */
    /* The caller has also replaced its measured gyro bias. Keeping Fusion's
     * residual from the OLD bias subtracts it again from the new zero and
     * manufactures rotation/linear acceleration while physically stationary. */
    FusionBiasSetOffset(&s->bias,zero);
    FusionAhrsRestart(&s->ahrs);
    for(unsigned i=0;i<300;++i)FusionAhrsUpdateNoMagnetometer(&s->ahrs,zero,a);
    FusionAhrsSkipStartup(&s->ahrs);
}
void companion_fusion_step(void *handle,const float gyro[3],const float accel[3],float dt,float gravity[3],float corrected[3]) {
    CompanionFusion *s=(CompanionFusion*)handle;
    FusionVector g={.array={gyro[0],gyro[1],gyro[2]}};
    const FusionVector a={.array={accel[0]*0.001f,accel[1]*0.001f,accel[2]*0.001f}};
    g=FusionBiasUpdate(&s->bias,g);
    FusionAhrsSetSamplePeriod(&s->ahrs,dt);
    FusionAhrsUpdateNoMagnetometer(&s->ahrs,g,a);
    const FusionVector up=FusionAhrsGetGravity(&s->ahrs);
    for(unsigned i=0;i<3;++i){gravity[i]=up.array[i];corrected[i]=g.array[i];}
}
void companion_fusion_desktop_step(void *handle,const float gyro[3],const float accel[3],float dt,bool correct_gravity,float earth[3],float gravity[3]) {
    CompanionFusion *s=(CompanionFusion*)handle;
    const float gain=correct_gravity?0.5f:0.0f;
    if(s->ahrs.gain!=gain){
        FusionAhrsSettings a=fusionAhrsDefaultSettings;a.sampleRate=1.0f/dt;a.gain=gain;
        a.gyroscopeRange=250.0f;a.accelerationRejection=10.0f;a.rejectionTimeout=5.0f;
        FusionAhrsSetSettings(&s->ahrs,&a);
    }
    float corrected[3];companion_fusion_step(handle,gyro,accel,dt,gravity,corrected);
    const FusionVector acceleration=FusionAhrsGetEarthAcceleration(&s->ahrs);
    for(unsigned i=0;i<3;++i)earth[i]=acceleration.array[i]*9.80665f;
}
