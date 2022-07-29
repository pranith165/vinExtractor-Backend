from cmath import nan
from django.shortcuts import render
from numpy import record
from pkg_resources import WorkingSet
from rest_framework import authentication, generics, permissions
from requests import get;
from requests import post;
from requests.exceptions import Timeout
from requests.exceptions import HTTPError
import pandas as pd;
import requests
import json
import xlsxwriter
from datetime import datetime
from bs4 import BeautifulSoup as bs
from django.http import JsonResponse
import configparser
import os

# info = get('https://maps.googleapis.com/maps/api/directions/json?origin=usf&destination=utd&key=AIzaSyCHK8W-Ag0zE7tk_YL1rIBHaZeM2a1kRGw')
# print(info.text) 
# Create your views here.

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

def process_NHTSA(word):
    if not pd.notnull(str(word)):
        return 'None'
    if "-" in word:
        word=word.split("-")[1].strip()
    if "/" in word:
        word=word.split("/")[0].strip()
    return word.lower()

def process_VIN(word):
    if not  pd.notnull(str(word)):
        return 'None'
    if "-" in word:
        word=word.split("-")[1].strip()
    if "/" in word:
        word=word.split("/")[0].strip()
    return word.lower()

@csrf_exempt
def GetMaps(request):
    #json parsers
    #maps hit
    #py manage.py makemigrations - shcema update
    #python3 manage.py migrate - database schema update
    #python3 manage.py runserver - run the django server
    #return JsonResponse(var)

    isNHTSA = request.POST['detailsNHTSA']
    isVindicator = request.POST['detailsVindicator']
    headerPresent = request.POST['headerPresent']
    columnsToIncludeString = request.POST['columnsToInclude']
    VINColumnName = request.POST['selectedVINColumn']

    #converting columns to include in excel file to json 
    columnsToInclude = []
    columnsToIncudeJSON = json.loads(columnsToIncludeString)
    for columns in columnsToIncudeJSON:
        columnsToInclude.append(columns["label"])

    excelData = pd.read_excel(request.FILES['selectedFile'])
    excelDataCheck = pd.read_excel(request.FILES['selectedFile'])
    data = pd.DataFrame()
    temp = pd.DataFrame()
    apiData = pd.DataFrame()
    scrapWebData = pd.DataFrame()

    # checking duplicate columns
    for column in excelData:
        if column.find('.') == True :
            responseText = { 
                "message": "Please Remove Duplicate column names",
                "value": "please"
            }
            # responseToSend = responseText.to_json(orient='records')
            return JsonResponse(data = responseText, status=203)


    #Calling api for batch size=50 everytime until last row. excelData.shape[0]-50
    if isNHTSA=='true':
        for i in range(0, excelData.shape[0]-50, 50):
            url=''
            for j in range(i, i+50):      
                if j <= (excelData.shape[0]-50)-1: 
                    url+=str(excelData.iloc[j][VINColumnName])+";"
            finalurl="https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVINValuesBatch/"      
            responseDataStatus = requests.post(finalurl,data={'DATA':url, 'FORMAT': 'JSON'})
            responseData = responseDataStatus.text
            if responseDataStatus.status_code != 200:
                print("error occured during the http call")
            y = json.loads(responseData)
            temp=temp.from_records(y['Results'])
            data=data.append(temp)


        url=''
        for i in range(excelData.shape[0]-50,excelData.shape[0]):
            # print(i)
            url+=str(excelData.iloc[i]['VIN'])+";"
        finalurl="https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVINValuesBatch/"
        response = requests.post(finalurl,data={'DATA':url, 'FORMAT': 'JSON'}).text
        y = json.loads(response)
        temp=temp.from_records(y['Results'])
        data=data.append(temp)

        # json response to send to frontend alternate option 
        returnResponse = data.to_json(orient='records')

        for x in columnsToInclude:
            data[x] = excelData[x]

        #adding data to apiData dataframe
        apiData = data

    scrapResponseDict = []
    if isVindicator=='true':
        # webscrapping logic starts here
        scrapObj = []

        # fetching HTML using beautiful soup
        def getHtml(vin):
            recurse = 0
            while recurse < 5:
                try:
                    html =  post("http://www.iihs-hldi.org/MotovinDirect.asp?ccr=EHS7N5F2F2L5&scr", data={"txtVIN":str(vin)}, timeout=2)
                    html = html.text
                    break
                except Timeout:
                    recurse += 1
                except:
                    recurse += 1
            if recurse >= 5:
                return ""
            else:
                return html 

        # setting up the headers
        header=[]
        html = getHtml("JS1GW71A962113563")
        while html == "":
            html = getHtml("JS1GW71A962113563")
        soup = bs(html, "lxml")
        header = header + ["ERROR", "Check Digit"] + [head.text for head, _ in zip(soup.find_all("strong"), range(18))]



        def getInfo(idVal, vin):
            scrapeDict = {}
            scrapeDict["ID"] = idVal
            scrapeDict["VIN"] = vin
            if len(str(vin)) == 17:
                html = getHtml(vin)
                soup = bs(html, "lxml")
                if html == "":
                    scrapeDict["ERROR"] = "Timeout Error"
                else:
                    try:
                        bTags = [b.text for b in soup.findAll("b")]

                        if "ERROR" in bTags:
                            scrapeDict["ERROR"] = bTags[bTags.index("ERROR") + 1]
                        else:
                            scrapeDict["ERROR"] = ""

                        scrapeDict["Check Digit"] = bTags[bTags.index("Check Digit") + 1]

                        wasHeaders = False

                        for table in soup.div.find_all("table"):
                            for tr in table.tr.find_all("tr"):
                                tdAll = [x.text for x in tr.find_all("td")]
                                allHeaders = all([td in header for td in tdAll])
                                if allHeaders:
                                    headersToUse = tdAll
                                    wasHeaders = True
                                elif wasHeaders:
                                    for td, head in zip(tdAll, headersToUse):
                                        scrapeDict[head] = td
                                    wasHeaders = False
                                else:
                                    for td in tdAll:
                                        if td in header:
                                            scrapeDict[td] = tdAll[tdAll.index(td) + 1]  
                        scrapObj.append(scrapeDict)
                    except:
                        print("Exception")
                        scrapeDict["ERROR"] = "WebPage Error"
                        scrapObj.append(scrapeDict)
            else:
                scrapeDict["ERROR"] = "VIN Error"
                scrapObj.append(scrapeDict)


        for i in range(0, excelData.shape[0]):
            vinNumber = excelData.iloc[i][VINColumnName]
            getInfo(i, vinNumber)

        #converting dictionary to dataframe
        scrapWebData = pd.DataFrame(scrapObj)
        for column in columnsToInclude:
            scrapWebData[column] = excelDataCheck[column]

    
    # # creating an excel to save the data
    # excelDirectory = 'static/excelOutput'
    # # excelDirectory = 'staticfiles/excelOutput'
    # excelFileName = "VinExtractor" + datetime.now().strftime("%m-%d-%y--%I-%M-%p")
    # # excelFileName = "VinExtractor"
    # downloadLink = excelDirectory+'/'+excelFileName
    # workbook = xlsxwriter.Workbook(excelDirectory+'/'+excelFileName+'.xlsx')
    # # workbook = xlsxwriter.Workbook('static/excelOutput/vinData.xlsx')
    # if isNHTSA=='true':
    #     NHTSAsheet = workbook.add_worksheet('NHTSA Data')
    #     # adding header to NHTSA excel sheet
    #     for i in range(len(apiData.columns)):
    #         NHTSAsheet.write(0, i, apiData.columns[i])
    #     # filling rows to the NHTSA sheets
    #     for i in range(apiData.shape[0]):
    #         for j in range(len(apiData.columns)):
    #             try:
    #                 NHTSAsheet.write(i+1, j, apiData.iloc[i][j])
    #             except:
    #                 pass


    # if isVindicator=='true':

        # validatind "HLDI Class Name" column
    #     HLDICheck = scrapWebData.columns
    #     if("HLDI Class Name" not  in HLDICheck):
    #         HLDIError = { 
    #             "message": "Please select correct VIN column for vindicator data",
    #             "value": "Please select correct VIN column"
    #         }
    #         # responseToSend = responseText.to_json(orient='records')
    #         return JsonResponse(data = HLDIError, status=203)

    #     Vindicator = workbook.add_worksheet('Vindicator Data')
    #     # adding header to Vindicator excel sheet
    #     for i in range(len(scrapWebData.columns)):
    #         Vindicator.write(0, i, scrapWebData.columns[i])
    #     # filling rows to the Vindicator sheets
    #     for i in range(scrapWebData.shape[0]):
    #         for j in range(len(scrapWebData.columns)):
    #             try:
    #                 Vindicator.write(i+1, j, scrapWebData.iloc[i][j])
    #             except:
    #                 pass

    compareResult = pd.DataFrame() 
    if(isNHTSA =='true' and isVindicator == 'true'):
        config = configparser.ConfigParser(allow_no_value=True)
        config.read('./helperProperties.ini')
        result=pd.DataFrame(columns=['BodyClass',"HLDI Class Name","Final"])
        data_NHTSA=apiData
        data_Vin=scrapWebData
        try:
            for x,y in zip(data_NHTSA['BodyClass'], data_Vin['HLDI Class Name']):
                x_processed=process_NHTSA(str(x))
                y_processed=process_VIN(str(y))
                try:
                    query1='('+str(x_processed)+","+'None'+')'
                    if bool(config['TrueRules'][query1])==True:
                        result=pd.concat([result,pd.DataFrame({"BodyClass":x,"HLDI Class Name":y,"Final":x_processed},index=[0])],ignore_index=True)
                        continue
                except:
                        print('')
                try:
                    query2='(' + "None"+","+ str(y_processed)+')'
                    if bool(config['TrueRules'][query2])==True:
                        result=pd.concat([result,pd.DataFrame({"BodyClass":x,"HLDI Class Name":y,"Final":y_processed},index=[0])],ignore_index=True)
                        continue
                except:
                    print('')
                try:
                    query='('+str(x_processed)+','+str(y_processed)+')'
                    result=pd.concat([result,pd.DataFrame({"BodyClass":x,"HLDI Class Name":y,"Final":config['mapping'][query]},index=[0])],ignore_index=True)
                    continue
                except:
                    result=pd.concat([result,pd.DataFrame({"BodyClass":x,"HLDI Class Name":y,"Final":"Rule not Found"},index=[0])],ignore_index=True)
        # result.to_excel("temp.xlsx")
            compareResult = result
        except:
            # workbook.close()
            vinColumnMatchError = { 
                "message": "Please select correct VIN column",
                "value": "please"
            }
            # responseToSend = responseText.to_json(orient='records')
            return JsonResponse(data = vinColumnMatchError, status=203)
            
        # compareSheet = workbook.add_worksheet('Compare')
        # # adding header to Vindicator excel sheet
        # for i in range(len(result.columns)):
        #     compareSheet.write(0, i, result.columns[i])
        # # filling rows to the Vindicator sheets
        # for i in range(result.shape[0]):
        #     for j in range(len(result.columns)):
        #         try:
        #             compareSheet.write(i+1, j, result.iloc[i][j])
        #         except:
        #             pass

    # workbook.close()



    # origin = request.GET.get('origin')
    # desti = request.GET.get('destination')
    # date = request.GET.get('departureTime')
    # model = request.GET.get('trafficModel')
    # print(date)
    # url = 'https://maps.googleapis.com/maps/api/directions/json?origin='+ origin + '&destination=' + desti + '&departure_time='+ date +'&trafficModel='+model+'&mode=driving' + '&key=AIzaSyCHK8W-Ag0zE7tk_YL1rIBHaZeM2a1kRGw'
    # info = get(url)
    # print(request.GET.get('origin'))
    # data = info.text
    # print(data)
    Comparedict = compareResult.to_json(orient = "records")
    NHTSAdict = data.to_json(orient = "records")
    scrapResponseDict = scrapWebData.to_json(orient="records")

    response = {
        'response_NHTSA' : NHTSAdict,
        'response_vindicator': scrapResponseDict,
        'response_Compare': Comparedict
    }
    # response = json.dumps(response, indent=4)
    return JsonResponse(data = response, status=200)
    
    return HttpResponse(downloadLink)
    
