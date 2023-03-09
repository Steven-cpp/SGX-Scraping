

import curses, time, os, sys
from time import sleep

def sp(str):
  for letter in str:
    sys.stdout.write(letter)
    sys.stdout.flush()
    time.sleep(0.5)
    
  print()

# to use it:
print('Start to download ', end=" ")
sp("...")


# def getNonTradDate(startDay):
#     rest_day = []
#     for i in range(startDay, 5369):
#         tc_url = f"{base_url}{i}/TC.txt"
#         dateStr = downloadFromUrl(tc_url, "./")[4:12]
#         cur =  datetime.strptime(dateStr, '%Y%m%d')
#         # Execute from second running
#         if (i > startDay):
#             deltaDays = (cur - pre).days
#             # Append all the rest days in the gap
#             if (deltaDays > 1):
#                 for j in range(1, deltaDays):
#                     rest_day.append(pre + timedelta(days=j))
#         pre = cur
#     with open('rest_days.pkl', 'wb') as f:
#         pickle.dump(rest_day, f)
# print(os.path.sep)

"""
    My      Actual
    05-19   05-18
    04-17   04-16
    03-17   03-16
    02-17   02-14 (4571)
            02-17 (4572)

            02-01 (4561) <-- Sat
    01-31   01-31 (4560) Friday  

        11-18   11-16 (4769)
        11-17   11-13 (4768)
(4767)  11-16   11-14 (4767) <-- Sat
(4766)  11-13         (4766) <-- 404 TO 4768
(4765)  11-12   11-12 (4765)
    10-30   10-30 (4756)

    
    4765 --> 11-12
    4766 --> Invalid
    4767 --> 11-14
    4768 --> 11-13
    4769 --> 11-16

"""