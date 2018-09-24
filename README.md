# bogame2

OGame bot

Requires a Chrome driver for selenium:
<http://chromedriver.chromium.org/downloads>

Example:

```bash
# Scan closest 100 inactive players with rank between 1000 and 2000, with 10
# missions at a time.
python3 scan.py \
-c=<country> -u=<email> -p=<password> \
--max_scans=100 \
--rank_min=1000 \
--rank_max=2000 \
--parallelism=10 \
--verbose=true

# Parse the last 100 scan reports and attack the 10 players with most crystal
# and no defense.
python3 attack.py \
-c=<country> -u=<email> -p=<password> \
--max_reports=100 \
--sort_by=crystal \
--num_attacks=10 \
--verbose=true
```

Example 2:

```bash
# Scan closest 100 players that are inactive, normal or honorable targets, with
# rank between 1000 and 2000, and 10 missions at a time.
# missions at a time.
python3 scan.py \
-c=<country> -u=<email> -p=<password> \
--include_inactive=true \
--include_normal=true \
--include_honorable=true \
--max_scans=100 \
--rank_min=1000 \
--rank_max=2000 \
--parallelism=10 \
--verbose=true

# Parse the last 100 scan reports and export them as CSV.
python3 attack.py \
-c=<country> -u=<email> -p=<password> \
--max_reports=100 \
--csv=reports.csv \
--verbose=true
```
