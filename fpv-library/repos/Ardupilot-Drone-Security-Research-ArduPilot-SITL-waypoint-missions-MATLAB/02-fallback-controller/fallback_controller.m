clc
clearvars
close all
addpath(genpath('ardupilot/libraries/SITL/examples/JSON/MATLAB/Copter'))

% =========================================================
%  FALLBACK CONTROLLER  —  Physics-aware PD implementation
%
%  Motor layout from Copter.m  (450 mm X-frame, NED frame):
%
%    ID  ch  Position          X(m)    Y(m)   dir
%    M1   1  front-right      +0.159  +0.159   -1  (CCW)
%    M2   4  rear-right       +0.159  -0.159   +1  (CW)
%    M3   2  rear-left        -0.159  -0.159   -1  (CCW)
%    M4   3  front-left       -0.159  +0.159   +1  (CW)
%
%  Physics convention from sim_multicopter.m:
%    moment_roll  = thrust * location(1)   [X arm]
%    moment_pitch = thrust * location(2)   [Y arm]
%    net roll  moment = -sum(moment_roll)  [negated]
%    net pitch moment = +sum(moment_pitch) [added]
%
%  DERIVED MIXING (proven from physics):
%
%  To correct positive roll (right tilt, roll>0):
%    Need net_roll_moment < 0
%    => Increase RIGHT motors (X>0): M1(ch1), M2(ch4)
%    => Decrease LEFT  motors (X<0): M3(ch2), M4(ch3)
%
%  To correct positive pitch (nose up, pitch>0):
%    Need net_pitch_moment < 0
%    => Increase REAR  motors (Y<0): M2(ch4), M3(ch2)
%    => Decrease FRONT motors (Y>0): M1(ch1), M4(ch3)
%
%  FINAL MIXING TABLE:
%    ch1 FR (X+,Y+):  PWM_HOVER + alt_corr + roll_corr - pitch_corr
%    ch4 RR (X+,Y-):  PWM_HOVER + alt_corr + roll_corr + pitch_corr
%    ch2 RL (X-,Y-):  PWM_HOVER + alt_corr - roll_corr + pitch_corr
%    ch3 FL (X-,Y+):  PWM_HOVER + alt_corr - roll_corr - pitch_corr
%
%  Hover PWM: mass=2kg, 4 motors -> throttle=53.9% -> PWM=1531
%
%  Trigger:   |roll|>45 deg OR |pitch|>45 deg
%  Recovery:  |roll|<10 deg AND |pitch|<10 deg
%  Attack:    60-deg roll injected at t=40s, cleared at t=45s
% =========================================================

try
    state = load('Hexsoon','copter');
catch
    run('Copter.m')
    fprintf('Could not find Hexsoon.mat file, running copter.m\n')
    return
end

state.environment.density = 1.225;
state.gravity_mss         = 9.80665;
max_timestep              = 1/50;
init_function             = @init;
physics_function          = @physics_step;

SITL_connector(state, init_function, physics_function, max_timestep);

% ---------------------------------------------------------
%  INIT
% ---------------------------------------------------------
function state = init(state)
    for i = 1:numel(state.copter.motors)
        state.copter.motors(i).rpm     = 0;
        state.copter.motors(i).current = 0;
    end
    state.gyro                = [0;0;0];
    state.dcm                 = diag([1,1,1]);
    state.attitude            = [0;0;0];
    state.accel               = [0;0;0];
    state.velocity            = [0;0;0];
    state.position            = [0;0;0];
    state.bf_velo             = [0;0;0];
    state.fallback_active     = false;
    state.fallback_start_time = 0;
    state.fallback_alt_target = 0;
    state.physics_time        = 0;

    fprintf('\n========================================\n')
    fprintf('[SYSTEM] Fallback controller ready\n')
    fprintf('[SYSTEM] Trigger  : |roll|>45 deg OR |pitch|>45 deg\n')
    fprintf('[SYSTEM] Recovery : |roll|<10 deg AND |pitch|<10 deg\n')
    fprintf('[SYSTEM] Attack   : 60-deg roll injected at t=40s\n')
    fprintf('[SYSTEM] You have 40s to arm, take off, reach altitude\n')
    fprintf('========================================\n\n')
end

% ---------------------------------------------------------
%  PHYSICS STEP
% ---------------------------------------------------------
function state = physics_step(pwm_in, state)

    state.physics_time = state.physics_time + state.delta_t;
    t = state.physics_time;

    % --------------------------------------------------
    %  SIMULATED CYBER-ATTACK at t=40s to t=45s
    %  Forces a 60-degree roll into both attitude AND DCM
    %  so the physics model sees a consistent orientation.
    % --------------------------------------------------
    if t >= 40.0 && t <= 45.0
        forced_roll = deg2rad(60);
        cr = cos(forced_roll); sr = sin(forced_roll);
        state.dcm = [1, 0,   0 ;
                     0, cr, -sr;
                     0, sr,  cr];
        state.attitude(1) = forced_roll;
        state.attitude(2) = 0;
    end

    state = check_fallback_condition(state);

    if state.fallback_active
        pwm_in = fallback_controller(state);
    end

    state.copter.battery.current = sum([state.copter.motors.current]);
    state.copter.battery.dropped_voltage = ...
        state.copter.battery.voltage - ...
        state.copter.battery.resistance * state.copter.battery.current;

    for i = 1:numel(state.copter.motors)
        motor = state.copter.motors(i);

        throttle = (pwm_in(motor.channel) - 1100) / 800;
        throttle = max(0, min(1, throttle));

        voltage = throttle * state.copter.battery.dropped_voltage;

        Kt      = 1 / (motor.electrical.kv * ((2*pi)/60));
        current = ((motor.electrical.kv * voltage) - motor.rpm) / ...
                  ((motor.electrical.resistance + motor.esc.resistance) * motor.electrical.kv);
        torque  = current * Kt;

        prop_drag = motor.prop.PConst * state.environment.density * ...
                    (motor.rpm/60)^2 * motor.prop.diameter^5;

        w   = motor.rpm * ((2*pi)/60);
        w1  = w + ((torque - prop_drag) / motor.prop.inertia) * state.delta_t;
        rps = max(0, w1 / (2*pi));

        thrust = 2.2 * motor.prop.TConst * state.environment.density * ...
                 rps^2 * motor.prop.diameter^4;

        state.copter.motors(i).torque       = torque;
        state.copter.motors(i).current      = current;
        state.copter.motors(i).rpm          = rps * 60;
        state.copter.motors(i).thrust       = thrust;
        state.copter.motors(i).moment_roll  = thrust * motor.location(1);
        state.copter.motors(i).moment_pitch = thrust * motor.location(2);
        state.copter.motors(i).moment_yaw   = -torque * motor.direction;
    end

    drag = sign(state.bf_velo) .* state.copter.cd .* state.copter.cd_ref_area .* ...
           0.5 .* state.environment.density .* state.bf_velo.^2;

    force = [0; 0; -sum([state.copter.motors.thrust])] - drag;

    rotational_drag = 0.2 * sign(state.gyro) .* state.gyro.^2;

    moments = [-sum([state.copter.motors.moment_roll]);
                sum([state.copter.motors.moment_pitch]);
                sum([state.copter.motors.moment_yaw])] - rotational_drag;

    state = update_dynamics(state, force, moments);

    if mod(round(t * 50), 100) == 0
        alt   = -state.position(3);
        roll  = rad2deg(state.attitude(1));
        pitch = rad2deg(state.attitude(2));
        if state.fallback_active
            fprintf('[FALLBACK ACTIVE] t=%5.1fs | Alt=%5.1fm (tgt=%.1fm) | Roll=%+6.1fdeg | Pitch=%+6.1fdeg\n', ...
                t, alt, state.fallback_alt_target, roll, pitch);
        else
            fprintf('[MAIN CTRL]       t=%5.1fs | Alt=%5.1fm | Roll=%+6.1fdeg | Pitch=%+6.1fdeg\n', ...
                t, alt, roll, pitch);
        end
    end
end

% ---------------------------------------------------------
%  CHECK FALLBACK CONDITION
% ---------------------------------------------------------
function state = check_fallback_condition(state)

    roll_deg  = rad2deg(state.attitude(1));
    pitch_deg = rad2deg(state.attitude(2));

    if abs(roll_deg) > 45 || abs(pitch_deg) > 45

        if ~state.fallback_active
            state.fallback_start_time = state.physics_time;
            state.fallback_alt_target = -state.position(3);

            fprintf('\n================================================\n')
            fprintf('[FALLBACK] *** TRIGGERED at t = %.2f s ***\n', state.physics_time)
            fprintf('[FALLBACK] Roll  = %+.1f deg  (limit: +/-45 deg)\n', roll_deg)
            fprintf('[FALLBACK] Pitch = %+.1f deg  (limit: +/-45 deg)\n', pitch_deg)
            fprintf('[FALLBACK] Altitude hold target: %.2f m\n', state.fallback_alt_target)
            fprintf('[FALLBACK] Main controller OVERRIDDEN\n')
            fprintf('================================================\n\n')
        end
        state.fallback_active = true;

    elseif state.fallback_active && abs(roll_deg) < 10 && abs(pitch_deg) < 10
        fprintf('\n================================================\n')
        fprintf('[FALLBACK] *** RECOVERED at t = %.2f s ***\n', state.physics_time)
        fprintf('[FALLBACK] Attitude stable — returning to main controller\n')
        fprintf('[FALLBACK] Roll  = %+.1f deg\n', roll_deg)
        fprintf('[FALLBACK] Pitch = %+.1f deg\n', pitch_deg)
        fprintf('================================================\n\n')
        state.fallback_active = false;
    end
end

% ---------------------------------------------------------
%  FALLBACK CONTROLLER
% ---------------------------------------------------------
function pwm_out = fallback_controller(state)

    Kp_roll  = 350;   Kd_roll  = 70;
    Kp_pitch = 350;   Kd_pitch = 70;
    Kp_alt   = 60;    Kd_alt   = 45;

    roll       = state.attitude(1);
    pitch      = state.attitude(2);
    roll_rate  = state.gyro(1);
    pitch_rate = state.gyro(2);
    alt        = -state.position(3);
    vert_vel   = -state.velocity(3);
    alt_target = state.fallback_alt_target;

    time_in_fb = state.physics_time - state.fallback_start_time;
    if time_in_fb < 1.5
        att_scale = 0.20 + 0.80 * (time_in_fb / 1.5);
        alt_scale = 0.60 + 0.40 * (time_in_fb / 1.5);
    else
        att_scale = 1.0;
        alt_scale = 1.0;
    end

    roll_corr  = Kp_roll  * roll  + Kd_roll  * roll_rate;
    pitch_corr = Kp_pitch * pitch + Kd_pitch * pitch_rate;

    roll_corr  = max(-300, min(300, roll_corr))  * att_scale;
    pitch_corr = max(-300, min(300, pitch_corr)) * att_scale;

    alt_err  = alt_target - alt;
    alt_corr = Kp_alt * alt_err - Kd_alt * vert_vel;
    alt_corr = max(-300, min(300, alt_corr)) * alt_scale;

    PWM_HOVER = 1531;
    PWM_MIN   = 1100;
    PWM_MAX   = 1900;

    pwm_ch1 = PWM_HOVER + alt_corr + roll_corr - pitch_corr;
    pwm_ch4 = PWM_HOVER + alt_corr + roll_corr + pitch_corr;
    pwm_ch2 = PWM_HOVER + alt_corr - roll_corr + pitch_corr;
    pwm_ch3 = PWM_HOVER + alt_corr - roll_corr - pitch_corr;

    pwm_out    = zeros(1, 4);
    pwm_out(1) = pwm_ch1;
    pwm_out(2) = pwm_ch2;
    pwm_out(3) = pwm_ch3;
    pwm_out(4) = pwm_ch4;

    pwm_out = max(PWM_MIN, min(PWM_MAX, pwm_out));

    fprintf('[FB t=%5.1fs scl=%.2f] ch1=%4d ch2=%4d ch3=%4d ch4=%4d | Alt=%4.1f/%.1fm Roll=%+5.1fd Pitch=%+5.1fd\n', ...
        state.physics_time, att_scale, ...
        round(pwm_out(1)), round(pwm_out(2)), round(pwm_out(3)), round(pwm_out(4)), ...
        alt, alt_target, rad2deg(roll), rad2deg(pitch));
end

% ---------------------------------------------------------
%  UPDATE DYNAMICS
% ---------------------------------------------------------
function state = update_dynamics(state, force, moments)
    rot_accel  = (moments' / state.copter.inertia)';
    state.gyro = state.gyro + rot_accel * state.delta_t;
    state.gyro = max(state.gyro, deg2rad(-2000));
    state.gyro = min(state.gyro, deg2rad(2000));

    [state.dcm, state.attitude] = rotate_dcm(state.dcm, state.gyro * state.delta_t);

    state.accel  = force / state.copter.mass;
    accel_ef     = state.dcm * state.accel;
    accel_ef(3)  = accel_ef(3) + state.gravity_mss;

    if state.position(3) >= 0 && accel_ef(3) > 0
        accel_ef(3) = 0;
    end

    state.accel    = state.dcm' * (accel_ef + [0;0;-state.gravity_mss]);
    state.velocity = state.velocity + accel_ef * state.delta_t;
    state.position = state.position + state.velocity * state.delta_t;

    if state.position(3) >= 0
        state.position(3) = 0;
        state.velocity     = [0;0;0];
        state.gyro         = [0;0;0];
    end

    state.bf_velo = state.dcm' * state.velocity;
end

% ---------------------------------------------------------
%  ROTATE DCM
% ---------------------------------------------------------
function [dcm, euler] = rotate_dcm(dcm, ang)
    delta = [...
        dcm(1,2)*ang(3)-dcm(1,3)*ang(2),  dcm(1,3)*ang(1)-dcm(1,1)*ang(3),  dcm(1,1)*ang(2)-dcm(1,2)*ang(1);
        dcm(2,2)*ang(3)-dcm(2,3)*ang(2),  dcm(2,3)*ang(1)-dcm(2,1)*ang(3),  dcm(2,1)*ang(2)-dcm(2,2)*ang(1);
        dcm(3,2)*ang(3)-dcm(3,3)*ang(2),  dcm(3,3)*ang(1)-dcm(3,1)*ang(3),  dcm(3,1)*ang(2)-dcm(3,2)*ang(1)];

    dcm = dcm + delta;
    a   = dcm(1,:);  b = dcm(2,:);
    err = a * b';
    t0  = a - b*(0.5*err);
    t1  = b - a*(0.5*err);
    t2  = cross(t0, t1);
    dcm(1,:) = t0/norm(t0);
    dcm(2,:) = t1/norm(t1);
    dcm(3,:) = t2/norm(t2);

    euler = [atan2(dcm(3,2), dcm(3,3));
            -asin(dcm(3,1));
             atan2(dcm(2,1), dcm(1,1))];
end
