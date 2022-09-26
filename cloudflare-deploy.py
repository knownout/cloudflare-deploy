import json
import os.path
import sys, re, requests


class ScriptArgumentsParser:
    """
    Utility class for parsing command line arguments
    """

    # Required arguments marked as none to prevent "Fiend not found" error
    Zone: str = None
    RecordName: str = None

    # Predefined arguments
    RecordType: str = "A"
    RecordProxied: bool = True
    RecordTTL: int = 1

    EraseMode: bool = False
    SilentMode: bool = False

    # Utility arguments to call specific functions
    ShowHelp: bool = False
    CallRegenerate: bool = False

    # Number of arguments that were successfully parsed
    TotalParsed = 0

    # Processor for cases where the user only needs to write a key without a value
    __ArgumentJustExist = lambda x: True

    # Map command line arguments to class fields with specific processing functions
    __ArgumentKeysMapping: dict[str, [str, any]] = {
        "zone": ["Zone", str],
        "name": ["RecordName", str],
        "ttl": ["RecordTTL", int],

        "type": ["RecordType", lambda x: str(x).upper()],

        "proxied": ["RecordProxied", __ArgumentJustExist],
        "erase": ["EraseMode", __ArgumentJustExist],
        "silent": ["SilentMode", __ArgumentJustExist],
        "help": ["ShowHelp", __ArgumentJustExist],
        "regenerate": ["CallRegenerate", __ArgumentJustExist]
    }

    def __init__(self):
        # Get list of arguments that starts from --
        argumentsList = list(filter(lambda x: len(x) > 1, " ".join(sys.argv[1:]).split("--")))

        for rawArgumentData in argumentsList:
            rawSplitArgumentData = rawArgumentData.strip().split(" ")

            # Handling case when an argument key is specified without data
            if len(rawSplitArgumentData) >= 2:
                [argumentKey, argumentData] = rawSplitArgumentData
            else:
                argumentKey = rawSplitArgumentData[0]
                argumentData = ""

            parsedArgumentData = str(argumentData).strip()

            try:
                if argumentKey in self.__ArgumentKeysMapping:
                    [parserClassField, argumentConvertFunction] = self.__ArgumentKeysMapping[argumentKey]
                    setattr(self, parserClassField, argumentConvertFunction(parsedArgumentData))
                    self.TotalParsed = self.TotalParsed + 1
            except:
                continue


class ScriptObjectRenderers:
    """
    Utility class for handling data returned by Cloudflare API or read from files
    """

    class CloudflareDNSResponseObject:
        """
        Utility class for handling data returned by Cloudflare Zone DNS API route
        """

        class CloudflareDNSResponseObjectMetaField:
            auto_added: bool
            managed_by_apps: bool
            managed_by_argo_tunnel: bool
            source: str

            def __init__(self, api_dict):
                for key in api_dict:
                    setattr(self, key, api_dict[key])

        def __init__(self, api_dict):
            for key in api_dict:
                if key == "meta":
                    setattr(self, key, self.CloudflareDNSResponseObjectMetaField(api_dict[key]))
                else:
                    setattr(self, key, api_dict[key])

        id: str
        zone_id: str
        zone_name: str
        name: str
        type: str
        content: str
        proxiable: bool
        proxied: bool
        ttl: int
        locked: bool
        meta: CloudflareDNSResponseObjectMetaField
        created_on: str
        modified_on: str

    class ScriptAPIConfigurationFile:
        """
        Utility class for handling data read from script configuration file
        """

        key: str
        hosting: str
        zones: dict[str, str]

        def __init__(self, file_json_content):
            for key in file_json_content:
                setattr(self, key, file_json_content[key])


class ScriptConfiguration:
    """
    Utility class for storing and processing all script data
    """

    # Cloudflare API access token that was read from a file
    __CloudflareAccessKey: str

    # Zones data from configuration file
    CloudflareZoneIDsList: dict[str, str]

    # Local machine (hosting) IP address from configuration file
    LocalMachineAddress: str

    # List of processed arguments
    Arguments: ScriptArgumentsParser


    def __init__(self, arguments: ScriptArgumentsParser):
        # Check if configuration file exist
        if not os.path.exists(os.path.join(os.getcwd(), "api-access.json")):
            raise Exception(f"Script configuration file not found, run script --regenerate to create a new one")

        configurationFileIO = open("api-access.json")

        try:
            configurationFile = ScriptObjectRenderers.ScriptAPIConfigurationFile(json.load(configurationFileIO))

            # Try to read keys from configuration file
            self.__CloudflareAccessKey = configurationFile.key
            self.CloudflareZoneIDsList = configurationFile.zones
            self.LocalMachineAddress = configurationFile.hosting

            self.Arguments = arguments

        except:
            raise Exception(f"Invalid configuration file given")

        finally:
            configurationFileIO.close()


        # Check if all required arguments are specified
        if self.Arguments.TotalParsed < 2:
            raise Exception(f"Given only {self.Arguments.TotalParsed} arguments while minimum two required")

        if not self.Arguments.Zone:
            raise Exception(f"Zone name not given within the arguments, add --zone argument to proceed")

        if not self.Arguments.RecordName:
            raise Exception(f"Record name not given within the arguments, add --name argument to proceed")

        if self.Arguments.Zone not in self.CloudflareZoneIDsList:
            raise Exception(f"Given unknown zone name alias: {self.Arguments.Zone}")

        if len(re.sub(r"[^A-z]", "", self.Arguments.RecordName)) < 3:
            raise Exception(f"Given invalid record name: {self.Arguments.RecordName}")


    def generateNewRecordOptions(self, private = False):
        """
        Method for generating API request parameters

        :return: API request options
        """

        recordOptions = {}
        recordOptions.update({
            "name": self.Arguments.RecordName,
            "type": self.Arguments.RecordType,
            "ttl": self.Arguments.RecordTTL,
            "proxied": self.Arguments.RecordProxied
        })

        if not private: recordOptions["content"] = self.LocalMachineAddress

        return recordOptions


    def sendCloudflareAPIRequest(self, method: str, json_data = None, erase = None):
        """
        Method for sending request to a Cloudflare API

        :param method: request HTTP method (GET, DELETE, POST, PUT, etc.)
        :param json_data: request data (POST, PUT, etc.)
        :param erase: erasing DNS record identifier
        :return: API response or exception
        """

        # Get zone id with specified alias
        cloudflareZoneID = self.CloudflareZoneIDsList[self.Arguments.Zone]

        dnsAPIRoute = f"https://api.cloudflare.com/client/v4/zones/{cloudflareZoneID}/dns_records{f'/{erase}' if erase else ''}"

        # Send request to the Cloudflare API
        response = requests.request(url=dnsAPIRoute, headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.__CloudflareAccessKey}'
        }, method=method, json=json_data)

        # Throw error if request not succeed
        if response.status_code != 200:
            raise Exception(f"Cloudflare API responses with error code: {response.status_code}")

        # Throw error if returned false success code
        response_json = response.json()
        if not response_json["success"]:
            raise Exception(f"Cloudflare API responses with error object: {response_json['errors']}")

        return response_json["result"]


def showHelp():
    """
    Function to display help page
    """

    helpPageText = """
Help menu for the Cloudflare DNS deployment script

i This script was made to automatically create DNS records during
the deployment of new sites via gitlab

List of available arguments:
  --zone [Required]
      Set zone alias defined in api-access.json file
    
  --name [Required]
      Set new record name (sub-domain for zone alias)
    
  --ttl [Optional, Default = 1]
      Set new record time to live (from 3600 to 86400, 1 - automatic)
    
  --type [Optional, Default = A]
      Set new DNS record type (A, AAAA, CNAME, ...)
    
  --proxied [Optional, Default = True]
      Set proxy enabled or disabled for new record
    
  --erase [Optional, Default = False]
      Erase specified proxy instead of creating it
    
  --silent [Optional, Default = False]
      Run script without any output except errors


Script configuration file (api-access.json) structure:
  key - Cloudflare API token
  hosting - IP address of the hosting machine
  zones - Dictionary with hostnames as keys and zone IDs as values
  
Use --regenerate argument to create stub api-access file if not exist

"""

    print(helpPageText)

def callRegenerate(arguments: ScriptArgumentsParser):
    """
    Function to regenerate script configuration file
    :param arguments: script arguments parser
    """

    # Check if configuration file already exist
    if os.path.exists(os.path.join(os.getcwd(), "api-access.json")):
        if not arguments.SilentMode:
            print(f"Cannot regenerate configuration file: already exist at {os.getcwd()}\n")
        exit(0)

    # Create new configuration file
    regeneratedFileIO = open(os.path.join(os.getcwd(), "api-access.json"), "w+")
    regeneratedFileIO.write(json.dumps({
        "key": "API_ACCESS_TOKEN",
        "hosting": "0.0.0.0",
        "zones": {
            "example.org": "API_ZONE_ID"
        }
    }, indent=4))

    regeneratedFileIO.close()
    if not arguments.SilentMode:
        print(f"New configuration file created at {os.getcwd()}\n")

def main():
    arguments = ScriptArgumentsParser()


    if arguments.ShowHelp:
        showHelp()
        exit(0)

    if arguments.CallRegenerate:
        callRegenerate(arguments)
        exit(0)

    # Initialize base script class
    scriptConfiguration = ScriptConfiguration(arguments)

    if not arguments.SilentMode: print(f"Requesting cloudflare DNS records list for a specific zone: " + \
          f"{scriptConfiguration.CloudflareZoneIDsList[arguments.Zone]}...")

    # Try to get existing DNS records from Cloudflare
    cloudflareDNSRecordsList: list[ScriptObjectRenderers.CloudflareDNSResponseObject] = []
    for rawDNSRecord in scriptConfiguration.sendCloudflareAPIRequest("GET"):
        cloudflareDNSRecordsList.append(ScriptObjectRenderers.CloudflareDNSResponseObject(rawDNSRecord))

    baseRecordName = str(arguments.RecordName).strip().lower().replace(f".{arguments.Zone}", "", 1)
    eraseDNSRecordID = ""

    # Check if specified record exist (or not exist for erase) in received records list
    if not arguments.EraseMode:
        for recordName in map(lambda record: record.name, cloudflareDNSRecordsList):
            if f"{baseRecordName}.{arguments.Zone}" == str(recordName).strip().lower():
                if not arguments.SilentMode:
                    print("Cloudflare DNS deployment script succeed:")
                    print(f" - Record already exist: {baseRecordName}.{arguments.Zone}")
                exit(0)
    else:
        dnsRecordExist = False
        for recordData in cloudflareDNSRecordsList:
            if f"{baseRecordName}.{arguments.Zone}" == str(recordData.name).strip().lower():
                dnsRecordExist = True
                eraseDNSRecordID = recordData.id
                break

        if not dnsRecordExist:
            if not arguments.SilentMode:
                print("Cloudflare DNS erase failed:")
                print(f" - Record not exist: {baseRecordName}.{arguments.Zone}")
            exit(0)

    if not arguments.SilentMode:
        print(f"Cloudflare DNS record {'erase' if arguments.EraseMode else 'creation'} request:")
        print("  ", scriptConfiguration.generateNewRecordOptions(True), "\n")

    # Try to create new or delete record
    if not arguments.EraseMode:
        scriptConfiguration.sendCloudflareAPIRequest("POST", scriptConfiguration.generateNewRecordOptions())

    else:
        if len(eraseDNSRecordID) < 1:
            raise Exception(f"Given invalid cloudflare DNS record identifier: {eraseDNSRecordID}")

        scriptConfiguration.sendCloudflareAPIRequest("DELETE", erase=eraseDNSRecordID)

    if not arguments.SilentMode:
        print("Cloudflare DNS deployment script succeed:")
        print(f" + {'Erased' if arguments.EraseMode else 'Created new'} DNS record: {baseRecordName}.{arguments.Zone}")


if __name__ == '__main__':
    main()
