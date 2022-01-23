import  os
import  json
from    collections     import  defaultdict


## Features
CONFIG_TRAIN_IO_FEATURES = {
    "input_folder_path": "./"
    "output_folder_path": "./",
}
CONFIG_GPU_ENVIRONMENT_FEATURES = {
    "b_use_gpu": True,
    "num_gpu": 1,
    "usage_gpu_list": [0],
}
CONFIG_DATASET_FEATURES = {
    "dataset_file_name": "dow30_2009_to_2020.csv",
    "b_use_technical_indicator": True,
    "b_use_volatility_index": True,
    "b_use_turbulence_index": True,
    "b_use_user_defined_index": True,
}
CONFIG_PORTFOLIO_FEATURES = {
    "ticker_list": [
        "AAPL"
    ],
}
CONFIG_STOCK_MARKET_FEATURES = {
    "max_num_stock_hold": 30,
    "max_normalized_share_size": 100,
    "initial_account_balance": 1000000,
    "transcation_fee_percent": 0.0001,
    "reward_scaling": 0.0001.
}

DEFAULT_TRAIN_CONFIG_FEATURES = defaultdict(bool, {
    **CONFIG_TRAIN_IO_FEATURES,
    **CONFIG_GPU_ENVIRONMENT_FEATURES,
    **CONFIG_DATA_SET_FEATURES,
    **CONFIG_PORTFOLIO_FEATURES,
    **CONFIG_STOCK_MARKET_FEATURES,
})


def decoder(obj):
    ''' decode object recursively
    '''
    for key, value in obj.items():
        if isinstance(value, dict):
            for subkey, subvalue in decoder(value):
                yield (subkey, subvalue)
        else:
            yield (key,value)


def getConfig(obj, EXEC_MODE):
    def _update(key, value):
        ''' Update value of default dictionary
        '''
        # ====> Some condition to verify value
        return value

    # Build feature dictionary
    DEFAULT_CONFIG_FEATURES = (
        DEFAULT_TRAIN_CONFIG_FEATURES if EXEC_MODE == "train"
        else DEFAULT_TEST_CONFIG_FEATURES
    )     

    # Build data base info dictionary
    for key, value in decoder(obj):
        DEFAULT_CONFIG_FEATURES[key] = _update(key, value)
   
    return DEFAULT_CONFIG_FEATURES


def setConfig(EXEC_MODE="train", 
              CONFIG_FILE_NAME="train_config.json"
             ):
    ''' Parsing configuration file (.json), one sets model environment
    '''
    # Set path of configuration file
    JSON_FILE_PATH = (
        os.path.dirname(os.path.realpath(__file__))
        + "/config/"
        + CONFIG_FILE_NAME
    )
    
    # Parse configuration from .json
    with open(JSON_FILE_PATH) as f:
        obj = json.load(f)

    # Update configuration
    config = getConfig(obj, EXEC_MODE)

    return config
