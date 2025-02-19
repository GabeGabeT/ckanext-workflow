from ckan.plugins.toolkit import  _, h, get_action
import ckan.logic as logic
import ckan.lib.navl.dictization_functions as dict_fns
from ckan.common import request
import ckan.lib.base as base
import ckan.lib.helpers as h


abort = base.abort
redirect = h.redirect_to

tuplize_dict = logic.tuplize_dict
clean_dict = logic.clean_dict
parse_params = logic.parse_params
NotFound = logic.NotFound
NotAuthorized = logic.NotAuthorized
ValidationError = logic.ValidationError


def _save_new(self, context, package_type=None):
    """ 
       This function is for monkey patching to PackageController of ckan core.
       We add new behavior value 'go-read' here for value of button 'save' to 
       redirect to read url to break the work flow.
    """
    # The staged add dataset used the new functionality when the dataset is
    # partially created so we need to know if we actually are updating or
    # this is a real new.
    is_an_update = False
    ckan_phase = request.params.get('_ckan_phase')
    from ckan.lib.search import SearchIndexError
    try:
        data_dict = clean_dict(dict_fns.unflatten(
            tuplize_dict(parse_params(request.POST))))
        if ckan_phase:
            # prevent clearing of groups etc
            context['allow_partial_update'] = True
            # sort the tags
            if 'tag_string' in data_dict:
                data_dict['tags'] = self._tag_string_to_list(
                    data_dict['tag_string'])
            if data_dict.get('pkg_name'):
                is_an_update = True
                # This is actually an update not a save
                data_dict['id'] = data_dict['pkg_name']
                del data_dict['pkg_name']
                # don't change the dataset state
                data_dict['state'] = 'draft'
                # this is actually an edit not a save
                pkg_dict = get_action('package_update')(context, data_dict)

                if request.params['save'] == 'go-metadata':
                    # redirect to add metadata
                    url = h.url_for(controller='package',
                                    action='new_metadata',
                                    id=pkg_dict['name'])
                elif request.params['save'] == 'go-read':
                    # redirect to read dataset, this is the new
                    # behavior for draft state.
                    url = h.url_for(controller='package',
                                    action='read',
                                    id=pkg_dict['name'])
                else:
                    # redirect to add dataset resources
                    url = h.url_for(controller='package',
                                    action='new_resource',
                                    id=pkg_dict['name'])
                redirect(url)
            # Make sure we don't index this dataset
            if request.params['save'] not in ['go-resource',
                                              'go-metadata']:
                data_dict['state'] = 'draft'
            # allow the state to be changed
            context['allow_state_change'] = True

        data_dict['type'] = package_type
        context['message'] = data_dict.get('log_message', '')
        pkg_dict = get_action('package_create')(context, data_dict)

        if ckan_phase:
            # redirect to add dataset resources
            url = h.url_for(controller='package',
                            action='new_resource',
                            id=pkg_dict['name'])
            redirect(url)

        self._form_save_redirect(pkg_dict['name'], 'new',
                                 package_type=package_type)
    except NotAuthorized:
        abort(403, _('Unauthorized to read package %s') % '')
    except NotFound, e:
        abort(404, _('Dataset not found'))
    except dict_fns.DataError:
        abort(400, _(u'Integrity Error'))
    except SearchIndexError, e:
        try:
            exc_str = unicode(repr(e.args))
        except Exception:  # We don't like bare excepts
            exc_str = unicode(str(e))
        abort(500, _(u'Unable to add package to search index.') + exc_str)
    except ValidationError, e:
        errors = e.error_dict
        error_summary = e.error_summary
        if is_an_update:
            # we need to get the state of the dataset to show the stage we
            # are on.
            pkg_dict = get_action('package_show')(context, data_dict)
            data_dict['state'] = pkg_dict['state']
            return self.edit(data_dict['id'], data_dict,
                             errors, error_summary)
        data_dict['state'] = 'none'
        return self.new(data_dict, errors, error_summary)

