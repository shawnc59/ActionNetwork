To generate an Action Network API token, click the _Details_ option from the main menu, then click _API & Sync_. On the following page will be a drop down to select the target group, and a box labeled _Your API Key_. First select the correct group from the drop down, then click the _Your API Key_ box. <br/>

If there has already been an API key generated for this group, it will be displayed.  If not, or you need to revoke/regenerate a new key, click the _Revoke & Generate New Key_ button.  Be certain to securely store this key as it provides wide ranging access to data in the associated group.

##### event-registrations.py

Before running, use `pip install -r requirements.txt` to install required packages. Must set environment variable AN_API_TOKEN to the value of the API key for the target group.

`./event-registrations.py`

###### References

<a href="https://actionnetwork.org/docs/">Action Network API and Webhooks -- Getting Started</a>