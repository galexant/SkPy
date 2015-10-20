import time
import datetime

from .conn import SkypeConnection
from .chat import SkypeUser, SkypeChat
from .event import SkypeEvent, SkypePresenceEvent, SkypeTypingEvent, SkypeNewMessageEvent, SkypeEditMessageEvent
from .util import lazyLoad, stateLoad

class Skype(object):
    def __init__(self, user=None, pwd=None, tokenFile=None):
        self.conn = SkypeConnection(user, pwd, tokenFile)
    @property
    @lazyLoad
    def user(self):
        """
        Lazy: retrieve the current user.
        """
        json = self.conn("GET", "https://api.skype.com/users/self/profile", auth=SkypeConnection.Auth.Skype).json()
        return SkypeUser(self, json, True)
    @property
    @lazyLoad
    def contacts(self):
        """
        Lazy: retrieve all contacts for the current user.

        The Skype API also provides suggestions within the same list -- these can be filtered by looking for authorised = True.
        """
        contacts = {}
        for json in self.conn("GET", "https://contacts.skype.com/contacts/v1/users/" + self.user.id + "/contacts", auth=SkypeConnection.Auth.Skype).json().get("contacts", []):
            if not json.get("suggested"):
                contacts[json.get("id")] = SkypeUser(self, json)
        contacts[self.user.id] = self.user
        return contacts
    @stateLoad
    def getChats(self):
        """
        Stateful: retrieve a list of recent conversations.

        Each conversation is only retrieved once, so subsequent calls may exhaust the set and return an empty list.
        """
        url = self.conn.msgsHost + "/conversations"
        params = {
            "startTime": 0,
            "view": "msnp24Equivalent",
            "targetType": "Passport|Skype|Lync|Thread"
        }
        def fetch(url, params):
            resp = self.conn("GET", url, auth=SkypeConnection.Auth.Reg, params=params).json()
            return resp, resp.get("_metadata", {}).get("syncState")
        def process(resp):
            chats = {}
            for json in resp.get("conversations", []):
                chats[json.get("id")] = SkypeChat(self, json)
            return chats
        return url, params, fetch, process
    @SkypeConnection.resubscribeOn(404)
    def getEvents(self):
        """
        Retrieve a list of events since the last poll.  Multiple calls may be needed to retrieve all events.

        If no events are currently available, the API will block for up to 30 seconds, after which an empty list is returned.

        If any event occurs whilst blocked, it is returned immediately.
        """
        events = []
        for json in self.conn("POST", self.conn.msgsHost + "/endpoints/SELF/subscriptions/0/poll", auth=SkypeConnection.Auth.Reg).json().get("eventMessages", []):
            resType = json.get("resourceType")
            res = json.get("resource", {})
            if resType == "UserPresence":
                ev = SkypePresenceEvent(self, json)
            elif resType == "NewMessage":
                msgType = res.get("messagetype")
                if msgType in ("Control/Typing", "Control/ClearTyping"):
                    ev = SkypeTypingEvent(self, json)
                elif msgType in ("Text", "RichText"):
                    if res.get("skypeeditedid"):
                        ev = SkypeEditMessageEvent(self, json)
                    else:
                        ev = SkypeNewMessageEvent(self, json)
                else:
                    ev = SkypeEvent(self, json)
            else:
                ev = SkypeEvent(self, json)
            events.append(ev)
        return events
    def setStatus(self, status):
        """
        Set the user's presence.
        """
        self.conn("PUT", self.conn.msgsHost + "/presenceDocs/messagingService", json={
            "status": status
        })
    def __str__(self):
        return "[{0}]\nUser: {1}".format(self.__class__.__name__, str(self.user).replace("\n", "\n" + (" " * 6)))
    def __repr__(self):
        return "{0}(user={1})".format(self.__class__.__name__, repr(self.user))
