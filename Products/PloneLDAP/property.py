from Products.CMFCore.utils import getToolByName
from Products.PluggableAuthService.utils import classImplements
from Products.PluggableAuthService.UserPropertySheet import UserPropertySheet
from Products.PlonePAS.interfaces.propertysheets import IMutablePropertySheet


class LDAPPropertySheet(UserPropertySheet):
    def __init__(self, id, user):
        self.id=id
        self.acl=self._getLDAPUserFolder(user)

        self._ldapschema=[(x['ldap_name'], x['public_name'],
                        x['multivalued'] and 'lines' or 'string') \
                    for x in self.acl.getSchemaConfig().values() \
                    if x['public_name']]

        properties=self._getCache(user)
        if properties is None:
            properties=self.fetchLdapProperties(user)
            if properties:
                self._setCache(user, properties)

        UserPropertySheet.__init__(self, id,
                schema=[(x[1],x[2]) for x in self._ldapschema], **properties)


    def fetchLdapProperties(self, user):
        ldap_user = self.acl.getUserById(user.getId())
        properties={}

        # Do not pretend to have any properties if the user is not in LDAP
        if ldap_user is None:
            raise KeyError, "User not in LDAP"

        for (ldapname, zopename, type) in self._ldapschema:
            if ldap_user._properties.get(ldapname, None) is not None:
                properties[zopename]=ldap_user._properties[ldapname]
            else:
                if type=='lines':
                    properties[ldapname]=[]
                else:
                    properties[ldapname]=""

        return properties


    def canWriteProperty(self, user, id):
        return not self.acl.read_only


    def setProperty(self, user, id, value):
        self.setProperties(user, {id:value})


    def setProperties(self, user, mapping):
        ldap_user = self.acl.getUserById(user.getId())

        schema=dict([(x[1], (x[0], x[2])) for x in self._ldapschema])
        changes={}

        for (key,value) in mapping.items():
            if key in schema and self._properties[key]!=value:
                if schema[key][1]=="lines":
                    value=[x.strip() for x in value]
                else:
                    value=[value.strip()]
                self._properties[key]=value
                changes[schema[key][0]]=value

        self.acl._delegate.modify(ldap_user.dn, attrs=changes)
	self.acl._expireUser(user.getUserName())
        self._invalidateCache(user)


    def _getLDAPUserFolder(self, user):
        """ Safely retrieve a (LDAP)UserFolder to work with """
        portal=getToolByName(user.acl_users, 'portal_url').getPortalObject()
        return portal.acl_users._getOb(self.id).acl_users


    def getLDAPMultiPlugin(self, user):
        return self._getLDAPUserFolder(user).aq_parent


    def _getUserPropertyCacheKey(self, user):
        """_getUserPropertyCacheKey(id) -> (view_name, keywords)

        given user id, return view_name and keywords to be used when 
        querying and storing into the user property cache
        """
        view_name = self.id + '__UserPropertyCache'
        keywords = { 'id' : user.getId() }
        return view_name, keywords


    def _invalidateCache(self, user):
        view_name, keywords = self._getUserPropertyCacheKey(user)
        ldapmp=self.getLDAPMultiPlugin(user)
        ldapmp.ZCacheable_invalidate(view_name=view_name)


    def _setCache(self, user, properties):
        """Cache user properties"""
        view_name, keywords = self._getUserPropertyCacheKey(user)
        ldapmp=self.getLDAPMultiPlugin(user)
        ldapmp.ZCacheable_set(properties, view_name=view_name, keywords=keywords)


    def _getCache(self, user, default=None):
        """Retrieve user properties from cache, given a user id.

        Returns None or the passed-in default if the cache
        has no group with such id
        """
        view_name, keywords = self._getUserPropertyCacheKey(user)
        ldapmp=self.getLDAPMultiPlugin(user)
        result = ldapmp.ZCacheable_get( view_name=view_name
                                    , keywords=keywords
                                    , default=default
                                    )
        return result



classImplements(LDAPPropertySheet,
                            IMutablePropertySheet)

