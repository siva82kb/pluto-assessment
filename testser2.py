import csv

fh = open("test.csv", "w", newline='')
wrtr = csv.writer(fh)
wrtr.writerows([["a", "b1", "c"]])
# fh.close()