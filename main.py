import requests
import shutil
from tqdm.auto import tqdm
import os
from datetime import datetime, timedelta
import pickle

BASE_DATE = datetime(2019, 5, 6)
BASE_DELTA = 4366
BAD_DATES = [datetime(2020, 2, 1), datetime(2020, 11, 13)]

# Convert `date` to days in SGX Derivitive hist data
def date2Deltadays(date: datetime) -> int:
    # [TODO: EXC] returned days could be out of range
    days_passed = (date - BASE_DATE).days
    n_rest = days_passed // 7 * 2
    rem = days_passed % 7
    if (rem < 5):
        delta_cur = BASE_DELTA + days_passed - n_rest
    else:
        delta_cur = BASE_DELTA + days_passed - n_rest - rem + 4
        print('==== Is Weekend ====')
    if (date >= BAD_DATES[0]):
        delta_cur += 1
    if (date >= BAD_DATES[1]):
        delta_cur += 2
    return delta_cur

day = 5361
base_url = "https://links.sgx.com/1.0.0/derivatives-historical/"

TYPE_DICT = {0: 'ALL', 1: 'HD', 2: 'TK', 3: 'TC', 4: 'DS'}
tc_ds_url = f"{base_url}{day}/TC_structure.dat"
tick_ds_url = f"{base_url}{day}/TickData_structure.dat"



def getHistData(dtype, start, end, save_dir="./"):
    # [TODO: EXC] (private) Ensure the validity of `start` and `end`
    if (dtype in [0, 4]):
        print('[INFO] DS already downloaded')
    for i in range(date2Deltadays(start), date2Deltadays(end) + 1):
        tc_url = f"{base_url}{i}/TC.txt"
        tick_url = f"{base_url}{i}/WEBPXTICK_DT.zip"
        if (dtype in [0, 1, 2]):
            downloadFromUrl(tick_url, save_dir)
        if (dtype in [0, 1, 3]):
            downloadFromUrl(tc_url, save_dir)
    print('Download Success')



"""
Download file from `url` using a streaming GET request, tracked with proress bar.

Parameter
---------
url : str
    download link of target file
parent_dir='./' : str
    target file will be saved under {parentdir}/{SAVE_DIR}
    ERROR, if `parent_dir` not exists
"""
def downloadFromUrl(url, parent_dir):
    SAVE_DIR = "histData"

    # [TODO: FT] Make it private and ensure the validity of input args 
    if (not os.path.exists(parent_dir)):
        print(f"ERROR: path '{parent_dir}' NOT EXISTS")
        exit(-1)
    dir = os.path.join(parent_dir, SAVE_DIR)

    with requests.get(url, stream=True, timeout=5) as r:
        # check header to get content length, in bytes
        size_expected = int(r.headers.get("Content-Length"))
        if (r.headers.get('Content-Disposition') is None):
            print(f'url = {url}')
            exit(-1)
        _, fname = r.headers['Content-Disposition'].split(';')
        fname = fname.replace('filename=', '').strip('"') 

        # implement progress bar via tqdm
        with tqdm.wrapattr(r.raw, "read", total=size_expected, desc="")as raw:    
            with open(f'{dir}{os.path.sep}{fname}', 'wb')as output:
                shutil.copyfileobj(raw, output)


if __name__ == "__main__":
    start = datetime(2022, 5, 10)
    end = datetime(2022, 5, 25)
    getHistData(1, start, end)
    
    print(date2Deltadays(end))


