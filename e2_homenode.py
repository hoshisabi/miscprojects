import requests
import os
import re
import time
from operator import itemgetter

# --- Configuration ---
USER = os.environ.get("E2_USERNAME")
PASSWD = os.environ.get("E2_PASSWORD")
LIST_LENGTH = 5

# Hardcode the URL of the User Search XML Ticker II
URL = (
    "https://www.everything2.com/index.pl?node_id=1291794"
    f"&op=login&user={USER}&passwd={PASSWD}&nolimit=1&nosort=1"
)


def fetch_data(url):
    """Fetches the content from the specified URL."""
    # The original Perl used 'curl', in Python we use 'requests'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        return None


def print_list(writeups, alignment, key, title, count):
    """
    Generates and prints the HTML list based on the sorting key.
    writeups: list of dicts (the writeups)
    alignment: "left" or "right"
    key: the dict key to check for ties
    title: the list title
    count: the number of items to display
    """
    # Sort the list based on the criteria used by the caller
    # In Perl, the sort happens before the call, but here we'll ensure it's
    # correctly truncated and grouped/tied afterward.

    # Grouping logic from Perl:
    # 1. Iterate through the *already sorted* list.
    # 2. Group items with the same value for the 'key' (v in Perl) until the list is full.
    # 3. Inside each group (items with same key value), re-sort by 'votes' descending.

    # Python-style implementation of the complex Perl grouping/sorting logic:

    # 1. Take only the top 'count' items from the input list.
    # The Perl code's logic is actually more complex regarding ties.
    # It ensures that if the Nth item is tied with the (N+1)th, the tie is included
    # even if it exceeds N. However, the original Perl logic seems to try and
    # re-implement a stable sort with secondary key (votes).

    # A simplified, correct Python approach for the tie-handling as intended by the output:
    # The input 'writeups' is already sorted by the main criteria.
    # We take the top 'count' writeups, but we must include all writeups tied
    # with the 'count'th item based on the 'key' (v).

    new_list = writeups[:count]

    if len(writeups) > count:
        # Check for ties with the last item in new_list
        last_item_key_value = new_list[-1][key]
        for item in writeups[count:]:
            if item[key] == last_item_key_value:
                new_list.append(item)
            else:
                break  # Stop checking once the key value changes

    print(f'<p align="{alignment}">')
    print(f'<b>{count} {title}</b><br>')

    for i, writeup in enumerate(new_list):
        tied = ""
        # Check for ties: compare the current item's key value to the previous and next
        # Python check for tie logic:
        # Tied with previous: if i > 0 and key value is same as previous
        if i > 0 and writeup[key] == new_list[i - 1][key]:
            tied = " (tied) "
        # Tied with next: if i < len(new_list) - 1 and key value is same as next
        elif i < len(new_list) - 1 and writeup[key] == new_list[i + 1][key]:
            tied = " (tied) "

        j = i + 1  # Position number

        cools = writeup.get("cools", 0)
        ctxt = ""
        if cools != 0:
            ctxt = f" <b>{cools}C!</b> "

        name = writeup['name']

        if alignment == "left":
            print(f'{j}{tied}[{name}]{ctxt}<br>')
        elif alignment == "right":
            print(f'{ctxt}[{name}]{tied}{j}<br>')

    print("</p>\n")


def main():
    """Main execution function."""

    txt = fetch_data(URL)
    if not txt:
        return

    # Split by the closing tag </wu> to process individual writeups
    wutxt_list = txt.split('</wu>')

    wus = []  # All writeups
    wus_votes = []  # Writeups with votes > 0

    for w in wutxt_list:
        # Use regex to extract attributes and name
        cools_match = re.search(r'cools="(\d+)"', w)
        up_match = re.search(r'up="(\d+)"', w)
        down_match = re.search(r'down="(\d+)"', w)

        # Regex for name: >(text excluding <> and parenthesis) (text in parenthesis)<
        name_match = re.search(r'>([^<>]+) \([^)]*\)<', w)

        cools = int(cools_match.group(1)) if cools_match else 0
        up = int(up_match.group(1)) if up_match else 0
        down = int(down_match.group(1)) if down_match else 0
        name = name_match.group(1).strip() if name_match else ""

        if name == "":
            continue

        votes = up + down

        writeup_data = {
            "cools": cools,
            "ups": up,
            "downs": down,
            "rep": up - down,
            "votes": votes,
            "name": name,
            "goodness": "undefined"  # Initialize for all
        }

        if votes > 0:
            goodness = up / votes
            writeup_data["goodness"] = goodness
            wus_votes.append(writeup_data.copy())  # Copy to ensure 'goodness' is correct

        # Append to the main list (even those with votes=0 or undefined goodness)
        wus.append(writeup_data)

    # Get GMT time string
    gmt = time.strftime("%a %b %d %H:%M:%S %Y", time.gmtime())

    print(f"(List generated {gmt} GMT ")
    print("by the [clientdev: Homenode List Generator|Homenode List Generator].")
    print("Goodness is the percentage of votes that are upvotes.)\n")

    # --- Print Lists ---

    # 1. Most Voted-Upon Writeups (Descending by votes)
    sorted_wus = sorted(wus, key=itemgetter("votes"), reverse=True)
    print_list(sorted_wus, "right", "votes", "Most Voted-Upon Writeups", LIST_LENGTH)

    # 2. Least Voted-Upon Writeups (Ascending by votes)
    sorted_wus = sorted(wus, key=itemgetter("votes"))
    print_list(sorted_wus, "left", "votes", "Least Voted-Upon Writeups", LIST_LENGTH)

    # 3. Highest Goodness Writeups (Descending by goodness, only wus_votes)
    # Note: Goodness is a float/number for wus_votes list
    sorted_wus_votes = sorted(wus_votes, key=itemgetter("goodness"), reverse=True)
    print_list(sorted_wus_votes, "right", "goodness", "Highest Goodness Writeups", LIST_LENGTH)

    # 4. Lowest Goodness Writeups (Ascending by goodness, only wus_votes)
    sorted_wus_votes = sorted(wus_votes, key=itemgetter("goodness"))
    print_list(sorted_wus_votes, "left", "goodness", "Lowest Goodness Writeups", LIST_LENGTH)

    # 5. Most Reputable Writeups (Descending by rep)
    sorted_wus = sorted(wus, key=itemgetter("rep"), reverse=True)
    print_list(sorted_wus, "right", "rep", "Most Reputable Writeups", LIST_LENGTH)

    # 6. Least Reputable Writeups (Ascending by rep)
    sorted_wus = sorted(wus, key=itemgetter("rep"))
    print_list(sorted_wus, "left", "rep", "Least Reputable Writeups", LIST_LENGTH)


if __name__ == "__main__":
    main()