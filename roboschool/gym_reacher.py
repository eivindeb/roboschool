from roboschool.scene_abstract import SingleRobotEmptyScene
from roboschool.gym_mujoco_xml_env import RoboschoolMujocoXmlEnv
import gym, gym.spaces, gym.utils, gym.utils.seeding
import numpy as np
import os, sys

class RoboschoolReacher(RoboschoolMujocoXmlEnv):
    '''
    Get the end of two-link robotic arm to a given spot.
    Similar to MuJoCo reacher. 
    '''
    def __init__(self):
        RoboschoolMujocoXmlEnv.__init__(self, 'reacher.xml', 'body0', action_dim=2, obs_dim=9)
        self.history = {}

    def create_single_player_scene(self):
        return SingleRobotEmptyScene(gravity=0.0, timestep=0.0165, frame_skip=1)

    TARG_LIMIT = 0.205
    def robot_specific_reset(self, state=None, target=None):
        if target is not None:
            t_x, t_y = target["x"], target["y"]
        else:
            t_x = self.np_random.uniform(low=-self.TARG_LIMIT, high=self.TARG_LIMIT)
            t_y = self.np_random.uniform(low=-self.TARG_LIMIT, high=self.TARG_LIMIT)
        self.jdict["target_x"].reset_current_position(t_x, 0)
        self.jdict["target_y"].reset_current_position(t_y, 0)
        self.fingertip = self.parts["fingertip"]
        self.target    = self.parts["target"]
        self.central_joint = self.jdict["joint0"]
        self.elbow_joint   = self.jdict["joint1"]

        if state is not None:
            c_j, e_j = state["c_j"], state["e_j"]
        else:
            c_j = self.np_random.uniform(low=-3.14, high=3.14)
            e_j = self.np_random.uniform(low=-3.14, high=3.14)
        self.central_joint.reset_current_position(c_j, 0)
        self.elbow_joint.reset_current_position(e_j, 0)
        self.history = {"success": []}

    def apply_action(self, a):
        assert( np.isfinite(a).all() )
        self.central_joint.set_motor_torque( 0.05*float(np.clip(a[0], -1, +1)) )
        self.elbow_joint.set_motor_torque( 0.05*float(np.clip(a[1], -1, +1)) )

    def calc_state(self):
        theta,      self.theta_dot = self.central_joint.current_relative_position()
        self.gamma, self.gamma_dot = self.elbow_joint.current_relative_position()
        target_x, _ = self.jdict["target_x"].current_position()
        target_y, _ = self.jdict["target_y"].current_position()
        self.to_target_vec = np.array(self.fingertip.pose().xyz()) - np.array(self.target.pose().xyz())
        return np.array([
            target_x,
            target_y,
            self.to_target_vec[0],
            self.to_target_vec[1],
            np.cos(theta),
            np.sin(theta),
            self.theta_dot,
            self.gamma,
            self.gamma_dot,
            ])

    def calc_potential(self):
        return -100 * np.linalg.norm(self.to_target_vec)

    def step(self, a):
        assert(not self.scene.multiplayer)
        self.apply_action(a)
        self.scene.global_step()

        state = self.calc_state()  # sets self.to_target_vec

        self.history["success"].append(np.linalg.norm(self.to_target_vec) < 0.01)
        info = {"is_success": self.history["success"][-1], "success_time_frac": np.mean(self.history["success"])}

        potential_old = self.potential
        self.potential = self.calc_potential()

        electricity_cost = (
            -0.10*(np.abs(a[0]*self.theta_dot) + np.abs(a[1]*self.gamma_dot))  # work torque*angular_velocity
            -0.01*(np.abs(a[0]) + np.abs(a[1]))                                # stall torque require some energy
            )
        stuck_joint_cost = -0.1 if np.abs(np.abs(self.gamma)-1) < 0.01 else 0.0
        self.rewards = [float(self.potential - potential_old), float(electricity_cost), float(stuck_joint_cost)]
        self.frame  += 1
        self.done   += 0
        self.reward += sum(self.rewards)
        self.HUD(state, a, False)
        return state, sum(self.rewards), False, info

    def camera_adjust(self):
        x, y, z = self.fingertip.pose().xyz()
        x *= 0.5
        y *= 0.5
        self.camera.move_and_look_at(0.3, 0.3, 0.3, x, y, z)

    def get_random_initial_states(self, n_states):
        obs, states = [], []

        for i in range(n_states):
            obs.append(self.reset())
            states.append({"state": {"c_j": self.central_joint.current_position()[0],
                                     "e_j": self.elbow_joint.current_position()[0]},
                           "target": {"x": self.jdict["target_x"].current_position()[0],
                                      "y": self.jdict["target_y"].current_position()[0]}})

        return obs, states
