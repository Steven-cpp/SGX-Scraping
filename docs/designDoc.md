# SGX Scraping Design



This is the next phase of screening process for the DTL Data Engineer Intern, using Python to download historical data on the [SGX website](https://www.sgx.com/research-education/derivatives) within a specified date range.

## I. Requirement

Design a job to download the following files daily from the above website:

1. `WEBPXTICK_DT-*.zip`
2. `TickData_structure.dat`
3. `TC_*.txt`
4. `TC_structure.dat`

As is shown in the following snapshot, each file corresponds to each drop down options in *Time and Sales Historical Data*.

![image-20230306093101769](https://raw.githubusercontent.com/Steven-cpp/myPhotoSet/main/image-20230306093101769.png)

Send us a **.tar.gz** or **.zip** file that contains all the relevant files that you would like to **submit before 11th March 11.59 pm**.

As the requirements document is very general and free, I have further refined the program's statute to take into account the actual requirements of use.

### 1. Input

This program shoule be run with command line arguments to pass in a `config` file. The file is used to set following parameters:

1. **Download Data Type `type`**

   ALL, Both, Tick, Trade Cancellation, Data Structure

2. **Time Range `range`**

   Two ways of specifying the time range are supported:  1) Start Date - End Date; 2) Last n trading days

3. **Root Path `root_path`**

   Root location for saving the downloaded file. Current directory by default.

4. **Patent Directory `parent_dir`**

   A new folder `parent_dir` will be created under the `root_path` for storage. That is, the final storage path is `root_path/parent_dir`.

5. **Log Output Location `output_loc`**

   By default,  `INFO` and above will be written to the console, while `DEGUG` and above be written to a file.

6. **Auto Retry `auto_retry`**

   Whether to automatically re-download failed files after the download has finished, or to request whether the user needs to re-download them. Defaults to `false` and returns after retrying `max_retry`.

7. **Max Retry Limits `max_retry`**

   Max number of unsuccessful download retries.

### 2. Output

The program requires the use of `logging` module to output runtime status information, including:

1. **[INFO] Run Phase**

   The current task being performed, and its progress. In total, there are 3 run phases as follows:

   1. **Initializing**

      This includes the checking of config parameters, and class variables initialization.

   2. **Downloading**

      Then, the corresponding requests can be sent with these parameters to download required files. For each file, its download progress is displayed and its success or failure message is returned.

      After all the jobs have been downloaded, the job summary is displayed, waiting for the user to indicate whether the failed files need to be re-downloaded.

   3. **Retrying**

      This stage is entered if there are recorded failed files and the user specifies to re-download.

2. **[Warning] File Download Failed**

   See Error Recovery (II.3) for more details

3. **[ERROR] Invalid Config Parameter **

   See Error Recovery (II.3) for more details

### 3. Exception Handling

In addition, consider the exceptions that the program may occur at runtime:

1. **User Interaction Exceptions**

   There may be problems with the config parameters set by the user, both in terms of type and logic. It is necessary to ensure that the config parameters are reasonable and correct before running the program.

2. **Data Download Exception**

   After requesting a download url, if the server returns something other than `200` or does not return after `timeout`, an exception should be thrown.

## II. Program Design

Following the general process of software engineering, once the requirements have been confirmed, it is time to design the software at the top level. We might as well start by implementing the core module of the software, which is to download files within a specified date range and display a progress bar. 

Based on this core functionality, we can then expand the modules for logging, parameter setting and exception handling.

### 1. Core Module

The core module refers to [How To: Progress Bars for Python Downloads](https://www.alpharithms.com/progress-bars-for-python-downloads-580122/), and uses the `request ` and `tqdm` library to download files from the specified url in stream and save them to the specified path.

As each file is assigned a file ID on the server, a download link to the file can be generated from that ID, and the file can be downloaded using `request.get(url)`. However, the user enters a `date` rather than a `fileId`, so the mapping between the two needs to be determined.

**date -> fileId**

At first, I assumed that data files would only be generated on trading days (`buis_day`) and that weekends and holidays (`rest_day`) would be skipped. To test this assumption, I downloaded the latest 100 days of files and observed that only weekend data was unavailable, while all other periods were available. To account for this, I decided to use the earliest Monday as the `BASE_DAY` and calculate the number of days that have passed since then (`passed_day`). By taking the remainder of `passed_day` divided by 7, I can determine if it's a weekend day (either 5 or 6). If it is, the day can be safely skipped.

Thus, I set the Monday before approximately 1000 trading days as the base date `BASE_DAY`, constraining start date cannot be earlier than `BASE_DAY`. To calculate `deltaDay` (also known as `fileId`) for any given day, the following formula can be used:

```python
days_passed = tarDay - BASE_DAY
n_rest = days_passed / 7 * 2
rem = days_passed % 7
if (rem < 5):
	delta_cur = delta_base + tarDay - BASE_DAY - n_rest
else:
  delta_cur = delta_base + tarDay - BASE_DAY - n_rest - rem + 4
```

But in fact, there were anomalies in the `delta_days` on the server, which were not as continuous and regular as the theory suggests. After 1 hour of trying, I found 2 anomalies, as follows:

```python
BAD_DATES = [datetime(2020, 2, 1), datetime(2020, 11, 13)]
```

Specifically, The thexoretical position for `2020-11-13` is unavailable, and the associated ID has been moved up 2 places to `4768`. In contrast, documents have been recorded for `2020-02-01` and `2020-11-14`, both of which are non-trading days that fall on a Saturday.

As a result, special treatment is required for these two dates. Since `2020-02-01` is a non-trading day but still has recorded documents, the `delta_days` value for that day and all subsequent days should be increased by 1 to account for an additional trading day. For `2020-11-13`, an adjustment of +2 is necessary to reflect the vacancy and surplus trading day.

Finally, the mapping function from `date` to `deltaDays` can be obtained:

```python
def date2Deltadays(date: datetime) -> int:
  """
  Convert `date` to days(fileId) in SGX Derivitive hist data

  Noted
  -----
  It converts weekend to last Friday. So when weekend is set as start date, 
  it is implicitly perceived as last friday.
  """
  days_passed = (date - BASE_DATE).days
  n_rest = days_passed // 7 * 2
  rem = days_passed % 7
  if (rem < 5):
    delta_cur = BASE_DELTA + days_passed - n_rest
  else:
    delta_cur = BASE_DELTA + days_passed - n_rest - (rem - 4)

  if (date >= BAD_DATES[0]):
    delta_cur += 1
  if (date >= BAD_DATES[1]):
    delta_cur += 2
  return delta_cur
```

At this point, the implementation of the core modules is almost complete.

### 2. Logging Module

Next, add the logging module to the current program. To isolate and organize the logging logic, I decided to **refactor my functions in an object-oriented manner**. So that I can encapsulate logging logic within a class, controling when, where, and how logs are generated, and ensure that they are consistent across this scraper.

This can be implemented by simply importing `logging` module, and set up `logger` instance within the class from user specified config file. By default, the level of the file handler is set to `DEBUG` and the level of the console handler is set `INFO`, which means only levels >= `INFO` will show up on the console, while levels  >= `DEBUG` will be written to the log file.

A typical log file looks like the  following (with the year-month-date removed), which consists of three stages, as is outlined in I.2:

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

### 3. Error Recovery

This program may encounter two types of errors: configuration errors and download errors, as is outlined in I.3.

Configuration errors are classified as `ERROR` since they are unrecoverable until the user fixes the configuration. To prevent such errors, the program strictly checks all configurations during the scraper initialization stage, verifying both their type and logic. Once, invalid argument is detected, the program will send error message, and then exit.

While download errors are classified as `WARNING`, since in most cases, they are recoverable, resolved by re-downloading failed files. When such exception occurs, the program records the failed files and awaits user instruction to redownload them at the end of the job.

### 4. Optimization

To further enhance the user experience and program efficiency, I have come up with three new features to add to this program:

1. **Latest N Days**

   I have implemented a feature that allows users to specify a time range using the 'latest_n' day format. This feature makes it easier for users to retrieve data from specific time periods without having to manually sift through the data themselves. With this feature, users can simply specify the number of days they want to retrieve data from, and the program will automatically retrieve the relevant data.

2. **Avoid DS File Redundancy**

   After comparing data structure (DS) files on 20 different days on the server, I discovered an interesting fact: they are all the same. And the downloaded DS file has no date suffix. As a result, I established that DS files on different dates are the same.

   Based on this insight, I optimized DS file downloads by downloading only one pair of DS files in the beginning, independent of the time range. This feature not only saves time and bandwidth by avoiding redundant attempts, but it also ensures that users are always getting the most up-to-date version of the data.

3. **File Exsistence Check**

   Finally, I added a file existence check feature that prevents the program from attempting to download a file that already exists. This feature helps to eliminate duplicate files and saves time by avoiding unnecessary downloads.

With these three features, this program might be more efficient and user-friendly.
