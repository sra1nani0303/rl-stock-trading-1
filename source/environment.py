import  os
import  sys
import  glob
import  pickle

import  pandas      as  pd

import  numpy           as  np
import  jax.numpy       as  jnp
from    jax             import  grad, jit, vmap

import  gym
from    gym             import  spaces, error
from    gym.utils       import  closer, seeding
from    gym.logger      import  deprecation


class Environment(gym.Env):
    ''' The main OpenAI Gym class. 
        
        It encapsulates an environment with arbitrary behind-the-scenes dynamics. 
        An environment can be partially or fully observed.
    
        The main API methods that users of this class need to know are:
            
            step
            reset
            render
            close
            seed

        And set the following attributes:
        
            action_space: 
                The Space object corresponding to valid actions
            observation_space: 
                The Space object corresponding to valid observations
            reward_range: 
                A tuple corresponding to the min and max possible rewards
    
        Note that a default reward range set to [-inf,+inf] already exists. 
        Set it if you want a narrower range.
        The methods are accessed publicly as "step", "reset", etc...
    '''
    def __init__(self, df, 
                       day=0,
                       STOCK_DIM=30,    # total number of stocks in our portfolio
                       HMAX_NORMALIZE=100,    # shares normalization factor, e.g.) 100 shares per trade
                       INITIAL_ACCOUNT_BALANCE=1000000,    # initial amount of money we have in our account
                       TRANSACTION_FEE_PERCENT=.0001,    # trasaction fee, e.g.) 0.1% resonable percentage
                       TUBULENCE_THRESHOLD=140,    # turbulence index: 90-150 reasonable threshold
                       REWARD_SCALING=1.e-4,    # reward scaling factor
                       EXEC_MODE="train"
                ):
        
        # Set parameter
        self.df = df 
        self.day = day
        
        # Set parameter
        self.STOCK_DIM = STOCK_DIM
        self.HMAX_NORMALIZE = HMAX_NORMALIZE
        self.INITITAL_ACCOUNT_BALANCE = INITIAL_ACCOUNT_BALANCE
        self.TRANSACTION_FEE_PERCENT = TRANSACTION_FEE_PERCENT
        self.TUBULENCE_THRESHOLD = THUBULENCE_THRESHOLD
        self.REWARD_SCALING = REWARD_SCALING
        self.EXEC_MODE = EXEC_MODE

        # Set subclasses
        '''
        The continous action space is normalized between -1 and 1 and scaled as
        'STOCK_DIM'

        The observation space is to be in (0, inf)
        len(observation_space) = (
            [Current Balance]
            + [prices: 1-30]
            + [owned shares: 1-30] 
            + [macd: 1-30]
            + [rsi: 1-30] 
            + [cci: 1-30] 
            + [adx: 1-30]
        )
        '''
        self.action_space = spaces.Box(low=-1, high=1, shape=STOCK_DIM)
        self.observation_space = spaces.Box(low=0, high=np.inf, shape=(181,))
        self.reward_range = (-np.inf, np.inf)
        
        # Declare metadata container
        self.metadata = {
            "render/mode": []
        }
       
        # Initialize state 
        _ = self.reset()
        
        # Get random number generator
        # see: https://github.com/openai/gym/blob/master/gym/utils/seeding.py
        self.rng, _ = seeding.np_random(seed)

    def reset(self):
        # Reset memorize all the total balance change
        self.assetMemory = [self.INITIAL_ACCOUNT_BALANCE]
        self.rewardMemory = []
        
        # Reset variables
        self.reward = 0
        self.turbulence = 0
        self.cost = 0
        self.numTrade = 0
        self.bTerminal = False
        self.data = self.df.loc[self.day, :]
        
        # Reset state
        self.state = (
            [INITIAL_ACCOUNT_BALANCE] 
            + self.data.adjcp.values.tolist()
            + [0]*STOCK_DIM 
            + self.data.macd.values.tolist()
            + self.data.rsi.values.tolist()
            + self.data.cci.values.tolist() 
            + self.data.adx.values.tolist()
        )

        return self.state

    def _sell_stock(self, index, action):
        if self.state[index+STOCK_DIM+1] <= 0:
            pass
        
        # perform sell action based on the sign of the action
        if (self.turbulence < self.TURBULENCE_THRESHOLD or 
            self.EXEC_MODE == "train"):
            #update balance
            self.state[0] += \
            self.state[index+1]*min(abs(action),self.state[index+STOCK_DIM+1]) * \
                 (1- TRANSACTION_FEE_PERCENT)
                
            self.state[index+STOCK_DIM+1] -= min(abs(action), self.state[index+STOCK_DIM+1])
            self.cost +=self.state[index+1]*min(abs(action),self.state[index+STOCK_DIM+1]) * \
                 TRANSACTION_FEE_PERCENT
            self.numTrade+=1
        else:    # if turbulence goes over threshold, just clear out all positions 
            #update balance
            self.state[0] += self.state[index+1]*self.state[index+STOCK_DIM+1]* \
                              (1- TRANSACTION_FEE_PERCENT)
            self.state[index+STOCK_DIM+1] =0
            self.cost += self.state[index+1]*self.state[index+STOCK_DIM+1]* \
                              TRANSACTION_FEE_PERCENT
            self.numTrade+=1
    
    def _buy_stock(self, index, action):
        # perform buy action based on the sign of the action
        if (self.turbulence < self.TURBULENCE_THRESHOLD or 
            self.EXEC_MODE == "train"):
            # perform buy action based on the sign of the action
            available_amount = self.state[0] // self.state[index+1]
            
            #update balance
            self.state[0] -= self.state[index+1]*min(available_amount, action)* \
                              (1+ TRANSACTION_FEE_PERCENT)

            self.state[index+STOCK_DIM+1] += min(available_amount, action)
            
            self.cost+=self.state[index+1]*min(available_amount, action)* \
                              TRANSACTION_FEE_PERCENT
            self.numTrade+=1

        
    def step(self, actions):
        self.bTerminal = self.day >= len(self.df.index.unique())-1

        if self.bTerminal:
            plt.plot(self.assetMemory,'r')
            plt.savefig('results/account_value_trade_{}_{}.png'.format(self.model_name, self.iteration))
            plt.close()
            
            df_total_value = pd.DataFrame(self.assetMemory)
            df_total_value.to_csv('results/account_value_trade_{}_{}.csv'.format(self.model_name, self.iteration))
            end_total_asset = self.state[0]+ \
            sum(np.array(self.state[1:(STOCK_DIM+1)])*np.array(self.state[(STOCK_DIM+1):(STOCK_DIM*2+1)]))
            
            df_total_value.columns = ['account_value']
            df_total_value['daily_return']=df_total_value.pct_change(1)
            sharpe = (4**0.5)*df_total_value['daily_return'].mean()/ \
                  df_total_value['daily_return'].std()
            
            return self.state, self.reward, self.bTerminal,{}

        else:
            actions = actions * HMAX_NORMALIZE
            if self.turbulence>=self.TURBULENCE_THRESHOLD :
                actions=np.array([-HMAX_NORMALIZE]*STOCK_DIM)
                
            begin_total_asset = self.state[0]+ \
            sum(np.array(self.state[1:(STOCK_DIM+1)])*np.array(self.state[(STOCK_DIM+1):(STOCK_DIM*2+1)]))
            
            argsort_actions = np.argsort(actions)
            
            sell_index = argsort_actions[:np.where(actions < 0)[0].shape[0]]
            buy_index = argsort_actions[::-1][:np.where(actions > 0)[0].shape[0]]

            for index in sell_index:
                self._sell_stock(index, actions[index])

            for index in buy_index:
                self._buy_stock(index, actions[index])

            self.day += 1
            self.data = self.df.loc[self.day,:]         
            self.turbulence = self.data['turbulence'].values[0]
            
            #load next state
            self.state =  [self.state[0]] + \
                    self.data.adjcp.values.tolist() + \
                    list(self.state[(STOCK_DIM+1):(STOCK_DIM*2+1)]) + \
                    self.data.macd.values.tolist() + \
                    self.data.rsi.values.tolist() + \
                    self.data.cci.values.tolist() + \
                    self.data.adx.values.tolist()
            
            end_total_asset = self.state[0]+ \
            sum(np.array(self.state[1:(STOCK_DIM+1)])*np.array(self.state[(STOCK_DIM+1):(STOCK_DIM*2+1)]))
            self.assetMemory.append(end_total_asset)
            
            self.reward = end_total_asset - begin_total_asset            
            self.rewardMemory.append(self.reward)
            self.reward = self.reward*REWARD_SCALING

        return self.state, self.reward, self.bTerminal, {}
   
    
    def render(self, mode="human"):
        ''' Renders the environment.
        
        The set of supported modes varies per environment. (And some
        environments do not support rendering at all.) By convention,
        if mode is:
        - human: render to the current display or terminal and
          return nothing. Usually for human consumption.
        - rgb_array: Return an numpy.ndarray with shape (x, y, 3),
          representing RGB values for an x-by-y pixel image, suitable
          for turning into a video.
        - ansi: Return a string (str) or StringIO.StringIO containing a
          terminal-style text representation. The text can include newlines
          and ANSI escape sequences (e.g. for colors).
        
        Note:
            Make sure that your class's metadata 'render.modes' key includes
              the list of supported modes. It's recommended to call super()
              in implementations to use the functionality of this method.
        
        Args:
            mode (str): the mode to render with
        
        Example:
        
        class MyEnv(Env):
            metadata = {'render.modes': ['human', 'rgb_array']}
            def render(self, mode='human'):
                if mode == 'rgb_array':
                    return np.array(...) # return RGB frame suitable for video
                elif mode == 'human':
                    ... # pop up a window and render
                else:
                    super(MyEnv, self).render(mode=mode) # just raise an exception
        '''
        
        return self.state


class Framework(gym.Env):
    ''' Wraps the environment to allow a modular transformation.
    
        This class is the base class for all wrappers. 
        The subclass could override some methods to change the behavior of 
        the original environment without touching the original code.
    '''
    def __init__(self, env):
        super(Framework, self).__init__()
        
        self.env = env

        # setter action_space, observation_space, reward_range, metadata, 
        self._action_space = None
        self._observation_space = None
        self._reward_range = None
        self._metadata = None
    
    def step(self, action):
        return self.env.step(action)

    #def reset(self, seed: Optional[int] = None, **kwargs):
    #    return self.env.reset(seed=seed, **kwargs)
    def reset(self):
        # Previous total asset
        self.assetMemory = [(
            self.previous_state[0]
            + sum(np.array(self.previous_state[1:STOCK_DIM+)])
                  * np.array(self.previous_state[STOCK_DIM+1:2*STOCK_DIM+1]))
        )]
        self.rewardMemory = []

        # Reset variable
        self.day = 0
        self.turbulence = 0
        self.cost = 0
        self.numTrade = 0
        self.bTerminal = False
        self.data = self.df.loc[self.day, :]

        #$ Reset state
        self.state = (
            [self.previous_state[0]]
            + self.data.adjcp.values.tolist()
            + self.previous_state[(STOCK_DIM+1):(STOCK_DIM*2+1)]
            + self.data.macd.values.tolist()
            + self.data.rsi.values.tolist()
            + self.data.cci.values.tolist()
            + self.data.adx.values.tolist()
        )

        return self.state

    def render(self, mode="human", **kwargs):
        return self.env.render(mode, **kwargs)

    def compute_reward(self, achieved_goal, desired_goal, info):
        return self.env.compute_reward(achieved_goal, desired_goal, info)
