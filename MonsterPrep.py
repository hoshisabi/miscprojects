currmonstername = ""
currmonster = list()
monsterlist = dict()

def printmonster(n):
    mon = monsterlist[n]
    print(n, " ", mon[0])
    print(mon[1], mon[2], mon[3])
    print(mon[4], mon[5], mon[6], mon[7], mon[8], mon[9], mon[10], mon[11], mon[12], mon[13], mon[14], mon[15])
    for x in range(16,len(mon)):
        print(mon[x])
    print()
    print("---------------------------------")
    print()

with open("descent-chapter2-monsters.txt", "r") as file:
    for line in file:
        text = line.strip()
        if (text):
            if (text.startswith("---")):
                if (currmonstername != ""):
                    monsterlist[currmonstername] = currmonster
                    currmonstername = ""
                    currmonster = list()
            elif (currmonstername == ""):
                currmonstername = text
            else:
                currmonster.append(text)

monsterlist[currmonstername] = currmonster


for k in sorted(monsterlist):
    printmonster(k)
