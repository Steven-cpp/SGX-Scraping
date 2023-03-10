from requests.exceptions import RequestException
from datetime import datetime, timedelta
import logging, logging.config
from tqdm.auto import tqdm
import requests
import shutil
import os
import json
import argparse


BASE_DATE = datetime(2019, 5, 6)
BASE_DELTA = 4366
MAX_DELTA_RANGE = 1000
DELTA_LEN = 4
BAD_DATES = [datetime(2020, 2, 1), datetime(2020, 11, 13)]
BAD_DELTAS = [4561, 4766]
TYPE_DICT = {0: 'ALL', 1: 'BOTH', 2: 'TICK', 3: 'TC', 4: 'DS'}
TYPE_NAME = ['WEBPXTICK_DT.zip', 'TC.txt', 'TickData_structure.dat', 'TC_structure.dat']
base_url = "https://links.sgx.com/1.0.0/derivatives-historical/"
tick_ds_url = f"{base_url}4182/{TYPE_NAME[2]}"
tc_ds_url = f"{base_url}4433/{TYPE_NAME[3]}"


class Scraper:
    """
    A simple scraper to download historical trading data in given time range

    Configs
    -------
    DTYPE : int ->> range(0, 5)
        kind of statistics to scrape
    START, END : datetime ->> between `BASE_DATE` AND Today
        target time range, can be `None` ONLY when `LATEST_N` set
    LATEST_N : int ->> range(1, 1000)
        last n trading days, can be `None` ONLY when `START` and `END` set
    MAX_RETRY : int -> range(1, 5)
        max retry attempts when download failed, 3 by default
    ROOT_PATH : str -> os.path.exists()
        root path of saved scraped files, cwd by default.
        noted the final save_path is `{ROOT_PATH}/{PARENT_DIR}`
    PARENT_DIR : str -> os.mkdir() can succeed
        parent dir of scraped files, 'histData' by default
    AUTO_RETRY : bool -> [NO constraint]
        whether automatically redownload recorded failed files:
            * True : redownload failed files at the end of the job
            * False: await further user instruction when the job finished

    Methods
    -------
    getHistData() -> None
        download required files specified by config file
    __downloadFromUrl(url, isRetry=False) -> Exception
        send get request with the given `url`, to download file
    __retryFailed() -> None
        retry recorded failed requests
    __date2Deltadays(date) -> int
        return corresponding days (fileId) in SGX Derivitive from `date`
    __deltadays2Date(days) -> datetime
        return corresponding date in SGX Derivitive from `days`
    __checkConfigArgs() -> None
        check the validity of input arguments, as stated in above `configs` section

    Eample Usage
    ------------
    >>> s = Scraper('config.json')
    >>> s.getHistData()
    [outputs for downloading job]
    """

    def __init__(self, config_file) -> None:
        # 1. Load logging configurations
        with open(config_file, 'r') as f:
            config = json.load(f)
        logging.config.dictConfig(config['logging'])
        self.config_path = config_file
        self.logger = logging.getLogger(__name__)
        self.logger.info('=====   Scraper Initializing   =====')
        self.logger.info('Logging module successfully configured')

        # 2. Load download configurations
        downloadArgs = config['download']
        self.DTYPE = downloadArgs['type']
        self.START = downloadArgs['start']
        self.END = downloadArgs['end']
        self.LATEST_N = downloadArgs['latest_n']
        self.MAX_RETRY = downloadArgs.get('max_retry', 3)
        self.ROOT_PATH = downloadArgs.get('root_path', "./")
        self.PARENT_DIR = downloadArgs.get('parent_dir', "histData")
        self.AUTO_RETRY = downloadArgs.get('auto_retry', False)
        self.__checkConfigArgs()
        self.logger.info('Download module successfully configured')

        # 3. Set member variables
        self.batch_size = 0
        self.iter = 0
        self.excFiles= []
        self.excFileUrls = []

        self.logger.info('Done! Scraper Initialized')

    
    def getHistData(self):
        """
        Download required files specified by config file
        """
        # 1.  Calculate total number of files
        deltaRange = range(self.__date2Deltadays(self.START), self.__date2Deltadays(self.END) + 1)
        self.batch_size = deltaRange[-1] - deltaRange[0] + 1
        # 1.1 Avoid requesting `BAD_DELTA`, which does not exist on server
        if (BAD_DELTAS[1] in deltaRange):
            self.batch_size -= 1
        # 1.2 `DTYPE`` 0 & 1 asks to download both Tick and TC files
        if (self.DTYPE in [0, 1]):
            self.batch_size *= 2
        # 1.3 For data structure file requests, fileNums add 2
        if (self.DTYPE == 0):
            self.batch_size += 2
        elif (self.DTYPE == 4):
            self.batch_size = 2
            deltaRange = []        

        # 2. Initialize tracking variables
        self.iter = 1
        self.iter_exc = 0
        self.excFiles= []
        self.excFileUrls = []

        # 3. Show job overview, await user confirm to start job
        self.logger.info('=====   Download History Data  =====')
        self.logger.info('Job Overview:')
        dateRangeStr = f"from {datetime.strftime(self.START, '%Y-%m-%d')} to {datetime.strftime(self.END, '%Y-%m-%d')}"
        self.logger.info(f'   Date Range : {dateRangeStr}')
        self.logger.info(f'   Data Type  : {TYPE_DICT[self.DTYPE]}')
        self.logger.info(f'   Total Nums : {self.batch_size}')
        self.logger.info(f'   Save Dir   : {os.path.join(self.ROOT_PATH, self.PARENT_DIR)}')
        doDownload = input('Do you want to start the above download jobs? (Y/YES start): ')
        if (doDownload not in ['Y', 'YES']):
            self.logger.info('exit: User chooses NOT to start download job')
            return

        # 4. Download structural data first, if needed
        self.logger.info('downloading structural data')
        if (self.DTYPE in [0, 4]):
            self.__downloadFromUrl(tc_ds_url)
            self.__downloadFromUrl(tick_ds_url)

        # 5. Then downlaod history data
        self.logger.info('downloading history data')
        for fileId in deltaRange:
            if (fileId == BAD_DELTAS[1]):
                continue
            tc_url = f"{base_url}{fileId}/{TYPE_NAME[1]}"
            tick_url = f"{base_url}{fileId}/{TYPE_NAME[0]}"
            if (self.DTYPE in [0, 1, 2]):
                self.__downloadFromUrl(tick_url)
                    
            if (self.DTYPE in [0, 1, 3]):
                self.__downloadFromUrl(tc_url)
        
        # 6. Show job result summary, await users confirm to retry failed requests, if not set `AUTO_RETRY`
        n_success = self.batch_size - len(self.excFiles)
        logging.info(f'Successfully downloaded {n_success} files; {len(self.excFiles)} files failed')
        if len(self.excFiles) > 0:
            logging.warning('Failed files: ' + str(self.excFiles))
            if (self.AUTO_RETRY):
                self.__retryFailed()
                return
            doRetry = input('Do you want to retry downloading failed files? (Y/YES do retry): ')
            if (doRetry == 'Y' or doRetry == 'YES'):
                logging.info('User choose to retry failed files')
                self.__retryFailed()
            else:
                logging.info('User choose NOT to retry failed files')
        
        logging.info('Done! Complete downloading history data.')

        

    def __checkConfigArgs(self):
        """
        Check the validity of config args, both in type and range, as stated in class doc
        """
        logging.info('checking download module configs...')
        try:
            if not isinstance(self.DTYPE, int) and self.DTYPE in range(0, 5):
                raise ValueError('DTYPE should be of type `int` and within [0, 5)')

            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if self.LATEST_N:
                if not (isinstance(self.LATEST_N, int) and self.LATEST_N < MAX_DELTA_RANGE):
                    raise ValueError(f'LATEST_N should be of type `int` and < {MAX_DELTA_RANGE}')
                self.useRange = False
                self.END = today - timedelta(days=1)
                self.START = self.__deltadays2Date(self.__date2Deltadays(self.END) - self.LATEST_N + 1)
                
                # Since 2021-11-13 corresponds to an empty `fileId`, delta of previous dates should add 1
                if (self.START <= BAD_DATES[1]):
                    self.START = self.__deltadays2Date(self.__date2Deltadays(self.END) - self.LATEST_N)
            elif self.START and self.END:
                self.START = datetime.strptime(self.START, '%Y-%m-%d')
                self.END = datetime.strptime(self.END, '%Y-%m-%d')
                if self.START >= self.END:
                    raise ValueError('START date should be earlier than END date')
                if self.START < BASE_DATE:
                    raise ValueError(f'START date should be after {datetime.strftime(BASE_DATE, "%Y-%m-%d")}')
                if self.END >= today:
                    raise ValueError(f'END date should be earlier than today ({datetime.strftime(today, "%Y-%m-%d")})')
                self.useRange = True
            else:
                raise ValueError('time range incomplete, please specify LATEST_N or [START, END]')
            
            if not self.MAX_RETRY:
                self.MAX_RETRY = 3
            elif not (isinstance(self.MAX_RETRY, int) and self.MAX_RETRY in range(1, 5)):
                raise ValueError('MAX_RETRY should be of type `int` and within [1, 5)')
            
            if not self.ROOT_PATH:
                self.ROOT_PATH = "./"
            elif not os.path.exists(self.ROOT_PATH):
                raise ValueError(f'ROOT_PATH {self.ROOT_PATH} not exists')
            
            if not self.PARENT_DIR:
                self.PARENT_DIR = "histData"
            elif isinstance(self.PARENT_DIR, str):
                dir = os.path.join(self.ROOT_PATH, self.PARENT_DIR)
                if not os.path.exists(dir):
                    os.mkdir(dir)
                    logging.info(f'created new directory `{self.PARENT_DIR}` under {self.ROOT_PATH}')
            
            if not(isinstance(self.AUTO_RETRY, bool)):
                raise ValueError(f'self.AUTO_RETRY {self.AUTO_RETRY} should be of type `bool`')
            
        except (ValueError, OSError) as e:
            logging.error(f'Invalid Configuration: {e}', exc_info=True)
            logging.info(f'Check {self.config_path} to fix this error')
            exit(-1)
    

    def __downloadFromUrl(self, url, isRetry=False):
        """
        Download file from `url` using a streaming GET request, tracked with proress bar.

        Parameter
        ---------
        url : str
            download link of target file
        parent_dir='./' : str
            target file will be saved under {parentdir}/{SAVE_DIR}
        """
        emsg = None
        fileId = url[len(base_url): len(base_url) + DELTA_LEN]
        tarDate = self.__deltadays2Date(int(fileId)).strftime('%Y%m%d')
        fname_exp = url[len(base_url) + DELTA_LEN + 1:]
        if url[-3:] == TYPE_NAME[0][-3:]:
            fname_exp = fname_exp[:-DELTA_LEN] + '-' + tarDate + fname_exp[-DELTA_LEN:]
        elif url[-3:] == TYPE_NAME[1][-3:]:
            fname_exp = fname_exp[:-DELTA_LEN] + '_' + tarDate + fname_exp[-DELTA_LEN:]

        dir = os.path.join(self.ROOT_PATH, self.PARENT_DIR)

        if os.path.exists(os.path.join(dir, fname_exp)):
            self.logger.info(f'{self.iter}/{self.batch_size}: {fname_exp} already downloaded')
            self.iter += 1
            return emsg

        try:
            with requests.get(url, stream=True, timeout=5) as r:
                # check header to get file size and file name
                size_expected = int(r.headers.get("Content-Length"))
                if (r.headers.get('Content-Disposition') is None):
                    raise RequestException('404, requested file NOT FOUND')
                _, fname = r.headers['Content-Disposition'].split(';')
                fname = fname.replace('filename=', '').strip()

                # implement progress bar via tqdm
                with tqdm.wrapattr(r.raw, "read", total=size_expected, desc="")as raw:    
                    with open(f'{dir}{os.path.sep}{fname}', 'wb')as output:
                        shutil.copyfileobj(raw, output)
            self.logger.info(f'{self.iter}/{self.batch_size}: {fname} downloaded')
        except RequestException as e:
            emsg = e
            if (not isRetry):
                self.excFiles.append(fname_exp)
                self.excFileUrls.append(url)
                self.logger.debug(f'Failed to access {url}: {e}', exc_info=False)
                self.logger.warning(f'{self.iter}/{self.batch_size} failed: {fname_exp}: {e}')
           
        self.iter += 1
        return emsg


    def __retryFailed(self):
        logging.info('===== Redownload Failed Files =====')
        n_fails = len(self.excFiles)
        success_id = []
        self.iter -= n_fails
        for (id, url) in enumerate(self.excFileUrls):
            logging.info(f'{id + 1}/{n_fails}: Redownloading {self.excFiles[id]}')
            for i in range(self.MAX_RETRY):
                emsg = self.__downloadFromUrl(url, isRetry=True)
                if(emsg is None):
                    logging.info(f'\t{i + 1}/{self.MAX_RETRY} attemp success')
                    success_id.append(id)
                    break
                else:
                    logging.info(f'\t{i + 1}/{self.MAX_RETRY} attemp failed: {emsg}')
        for (cnt, id) in enumerate(success_id):
            del self.excFiles[id - cnt]
            del self.excFileUrls[id - cnt]
        logging.info(f'Successfully redownloaded {n_fails - len(self.excFiles)} files; {len(self.excFiles)} files still failed')
        


    def __date2Deltadays(self, date: datetime) -> int:
        """
        Convert `date` to days(fileId) in SGX Derivitive hist data

        Noted
        -----
        It converts weekend to last Friday. So when weekend is set as start date, it is 
        implicitly perceived as last friday.
        """
        days_passed = (date - BASE_DATE).days
        n_rest = days_passed // 7 * 2
        rem = days_passed % 7
        if (rem < 5):
            delta_cur = BASE_DELTA + days_passed - n_rest
        else:
            delta_cur = BASE_DELTA + days_passed - n_rest - (rem - 4)
            # print('==== Is Weekend ====')
        if (date >= BAD_DATES[0]):
            delta_cur += 1
        if (date >= BAD_DATES[1]):
            delta_cur += 2
        return delta_cur
    
    
    def __deltadays2Date(self, days: int) -> datetime:
        """
        Reversed operation of `__date2Deltadays()`, parse `days` to date
        """
        n_diff = days - BASE_DELTA
        rest_days = n_diff // 5 * 2
        res_date = BASE_DATE + timedelta(days=rest_days+n_diff)
        if (res_date >= BAD_DATES[0]):
            rest_days -= 1
            if (n_diff % 5 == 0 and days < BAD_DELTAS[1]):
                rest_days -= 2
        if (days >= BAD_DELTAS[1]):
            if (days == BAD_DELTAS[1]):
                logging.error('accessed bad delta')
            elif (days != BAD_DELTAS[1] + 1):
                rest_days -= 2

            if (n_diff % 5 in [0, 1, 2]):
                rest_days -= 2

        return BASE_DATE + timedelta(days=rest_days+n_diff)


if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description="Scraper config file")
    # parser.add_argument("configPath", help="Path of json file to config scraper")
    # args = parser.parse_args()
    # s = Scraper(args.configPath)

    s = Scraper('config.json')
    s.getHistData()
    
    
    


