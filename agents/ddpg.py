from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library
from builtins import super
standard_library.install_aliases()

import numpy as np
import chainer.links as L
import chainer.functions as F
from chainer import cuda

from . import dqn


class DDPG(dqn.DQN):
    """Deep Deterministic Policy Gradients.
    """

    def __init__(self, model, actor_optimizer, critic_optimizer, replay_buffer,
                 gamma, explorer, **kwargs):
        super().__init__(model, None, replay_buffer, gamma, explorer, **kwargs)

        # Aliases for convenience
        self.q_function = self.model['q_function']
        self.policy = self.model['policy']
        self.target_q_function = self.target_model['q_function']
        self.target_policy = self.target_model['policy']

        self.actor_optimizer = actor_optimizer
        self.critic_optimizer = critic_optimizer

    def update(self, experiences, errors_out=None):
        """Update the model from experiences
        """

        batch_size = len(experiences)

        # Store necessary data in arrays
        batch_state = self._batch_states(
            [elem['state'] for elem in experiences])

        batch_actions = self.xp.asarray(
                [elem['action'] for elem in experiences])

        batch_next_state = self._batch_states(
            [elem['next_state'] for elem in experiences])

        batch_rewards = self.xp.asarray(
            [[elem['reward']] for elem in experiences], dtype=np.float32)

        batch_terminal = self.xp.asarray(
            [[elem['is_state_terminal']] for elem in experiences],
            dtype=np.float32)

        # Update Q-function
        next_actions = self.target_policy(batch_next_state)
        next_q = self.target_q_function(batch_next_state, next_actions,
                                        test=True)

        target_q = batch_rewards + self.gamma * (1.0 - batch_terminal) * next_q
        target_q.unchain_backward()

        predict_q = self.q_function(batch_state, batch_actions, test=False)

        critic_loss = F.mean_squared_error(target_q, predict_q)

        self.critic_optimizer.zero_grads()
        critic_loss.backward()
        self.critic_optimizer.update()

        # Update policy
        q = self.q_function(batch_state, self.policy(batch_state))
        # Since we want to maximize Q, loss is negation of Q
        actor_loss = - F.sum(q) / batch_size

        self.actor_optimizer.zero_grads()
        actor_loss.backward()
        self.actor_optimizer.update()

    def select_action(self, state):

        def greedy_action():
            s = self._batch_states([state])
            action = self.policy(s)
            # Q is not needed here, but log it just for information
            q = self.q_function(s, action)
            self.logger.debug('t:%s a:%s q:%s',
                              self.t, action.data[0], q.data)
            return cuda.to_cpu(action.data[0])

        action = self.explorer.select_action(self.t, greedy_action)

        return action

