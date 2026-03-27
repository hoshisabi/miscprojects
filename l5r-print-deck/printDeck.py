# Much of this code is copied from https://gitorious.org/l5r-deck-printer

import urllib2
import urllib
import re
import sys
from xml.dom import minidom

def getCardUrl(cardName):
	url = 'http://imperialassembly.com/oracle/dosearch/'
	user_agent = 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
	header = { 'User-Agent' : user_agent }

	print >> sys.stderr, cardName
	if cardName.startswith("!"):
	  return cardName[1:]
	
	if not ' - ' in cardName:
		values = {
		  'search_13': cardName
		}
	else:
		splittedName = re.split(' - ', cardName)
		cardName = splittedName[0]
		if bool(re.search("inex", splittedName[1], re.I)):
			xpKeyword = "Inexperienced"
		elif bool(re.search("com", splittedName[1], re.I)):
			xpKeyword = "ExperiencedCoM"
		else:
			xpKeyword = "Experienced"
		m = re.search('\d', splittedName[1])
		if m != None:
			xpLevel = m.group(0)
			xpKeyword+= ' '+xpLevel
		values = {
		  'search_13': cardName,
		  'search_7':xpKeyword
		}
		cardName = cardName+" &#149; "+ xpKeyword

	#print values
	#cardId = "102012"

	data = urllib.urlencode(values)
	# req = urllib2.Request(url+data, None, header) # GET works fine
	req = urllib2.Request(url, data, header)  # POST request doesn't not work

	htmlResponse = urllib2.urlopen(req)
	cardString = htmlResponse.read()

	if '<tr class="pageheader">' in cardString:
		lines = re.split('\n', cardString)
		for line in lines:	
			if '<span class="l5rfont">'+cardName+'</span>' in line:
				cardString = line

	cardId =re.findall(r'#cardid=(\d+),', cardString)[0]

	url = 'http://imperialassembly.com/oracle/docard/'
	#user_agent = 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
	user_agent = 'Mobile Script'
	header = { 'User-Agent' : user_agent }
	values = {
		'cardid': cardId,
	}

	data = urllib.urlencode(values)
	# req = urllib2.Request(url+data, None, header) # GET works fine
	req = urllib2.Request(url, data, header)  # POST request doesn't not work

	htmlResponse = urllib2.urlopen(req)
	cardString = htmlResponse.read()

	cardUrl = re.findall(r'src="(.*?)"', cardString)[0]

	return cardUrl

def loadXml():
	#doc = minidom.parse("C:/Program Files (x86)/Egg of P'an Ku/cards-complete.xml")
	#doc.
	pass
	
# def getCardId(cardName):
	# print cardName
	
	# return "10219"
def getHtmlForCard(cardUrl, cardName):
	return '<img src="http://imperialassembly.com/oracle/'+ cardUrl +'" style="width:58mm;height:75mm" alt="' + cardName + '"/>\n'
#	return '<img src="http://imperialassembly.com/oracle/showimage?prefix=printing&cardid='+cardId+'&nestid=1&class=details&tagid=34" style="width:62mm;height:80mm"></img>'


def getCards(file):
	raw = file.readlines()
	result = {}
	for line in raw:
		line = line.strip()
		if line == "":
			continue
		if line.startswith("#"):
			continue		
		m = re.match('([0-9 ]+)(?:[-x ])* (.*)(?:<br/>)*', line)
		if m !=None:
			number = m.group(1)
			name = m.group(2)
			result[name] = number
		else:
			m = re.match('<h3><u>([^\(]+)</u></h3>', line)
			if m !=None:
				name = m.group(1)
				result[name] = 1
			else:
				name = line
				result[name] = 1
			
	return result

def getDeck(cardInstances):
	loadXml
	cardCount = 0
	result=""
	for cardName in cardInstances.keys():
		cardId = getCardUrl(cardName)
		nbCards = int(cardInstances[cardName])
		for i in range(0, nbCards):
			result+=getHtmlForCard(cardId, cardName)
			cardCount+=1
#			if (cardCount % 9) == 0:
#				result += '<DIV style="page-break-after:always"> </DIV>'
#			if (cardCount % 3) == 0:
#				result+='</br>'
	return result

filename = sys.argv[1]
file=open(filename, 'r')
cardInstances = getCards(file)
print getDeck(cardInstances)
