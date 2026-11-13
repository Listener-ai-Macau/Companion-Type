// Companion axis/unit adapter only. The mapped algorithm is unchanged upstream.
#include "GamepadMotion.hpp"
extern "C" void companion_player_space(const float* gyro, const float* up, float* result) {
    float pitch, yaw;
    // Companion: X right, +Y Type-C front, Z up. Upstream: Y up, gravity DOWN.
    // Proper right-handed basis change: (X,Y,Z) -> (X,Z,-Y).
    GamepadMotion::CalculatePlayerSpaceGyro(pitch,yaw,
        gyro[0],gyro[2],-gyro[1],-up[0],-up[2],up[1]);
    result[0]=yaw; result[1]=pitch;
}
