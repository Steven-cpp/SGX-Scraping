# SGX Scraping

This is my mini-project to download time and sales historical data on the [SGX website](https://www.sgx.com/research-education/derivatives) within a specified date range. It can download the following files for the **past 1000 market days**:

1. `WEBPXTICK_DT-*.zip`
2. `TickData_structure.dat`
3. `TC_*.txt`
4. `TC_structure.dat`

## Features

This scraper program is designed to provide a flexible and efficient way to download required data files, with the following features:

- **Flexible time range options**: user can either set specific start and end dates, or simply specify the number of market days they want to reterive data from.
- **Smart mapping**: the bidirectional mapping relationship of date and fileId has been well established and applied.
- **Detailed logging**: clear record of each running stage and important operation.
- **Storage-efficient**: by estabilishing the consistency of data structure files, and checking existance before downloading, this scraper saves time and bandwidth by avoiding redundant attempts.
- **Adequate exception handling**: with strict checking of configuration parameters and  download failing precautions, this scraper can always run as expected, even in the event of errors or exceptions.

## Getting Started

After cloning this repo, this program can be run with command line arguments, with a given `config` file:

```bash
git clone https://github.com/Steven-cpp/SGX-Scraping.git
cd SGX-Scraping
python main.py config.json
```

For example, if I want to download all the files (4 data types) from `2022-12-15` to `2022-12-31`, then I just need to specify the following parameters in the `config.json`:

```json
"download": {
  "type": 0,
  "start": "2022-12-15",
  "end": "2022-12-31"
}
```

With other default parameters in place, the program will run smoothly as shown below:

```python
10:14:06 - __main__ - INFO - =====   Scraper Initializing   =====
10:14:06 - __main__ - INFO - Logging module successfully configured
10:14:06 - root - INFO - checking download module configs...
10:14:06 - __main__ - INFO - Download module successfully configured
10:14:06 - __main__ - INFO - Done! Scraper Initialized
10:14:06 - __main__ - INFO - =====   Download History Data  =====
10:14:06 - __main__ - INFO - Job Overview:
10:14:06 - __main__ - INFO -    Date Range : from 2023-02-24 to 2023-03-09
10:14:06 - __main__ - INFO -    Data Type  : ALL
10:14:06 - __main__ - INFO -    Total Nums : 22
10:14:06 - __main__ - INFO -    Save Dir   : /Users/shiqi/Desktop/Projects/histData
10:14:07 - __main__ - INFO - downloading structural data
10:14:07 - __main__ - INFO - 1/22: TC_structure.dat already downloaded
10:14:07 - __main__ - INFO - 2/22: TickData_structure.dat already downloaded
10:14:07 - __main__ - INFO - downloading history data
10:14:07 - __main__ - INFO - 3/22: WEBPXTICK_DT-20230224.zip already downloaded
10:14:07 - __main__ - INFO - 4/22: TC_20230224.txt already downloaded
...
10:14:07 - root - INFO - Successfully downloaded 22 files; 0 files failed
10:14:07 - root - INFO - Done! Complete downloading history data.
```



