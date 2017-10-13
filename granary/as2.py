"""Convert between ActivityStreams 1 and 2.

AS2: http://www.w3.org/TR/activitystreams-core/

AS1: http://activitystrea.ms/specs/json/1.0/
     http://activitystrea.ms/specs/json/schema/activity-schema.html
"""
import copy
import logging

from oauth_dropins.webutil import util

CONTEXT = 'https://www.w3.org/ns/activitystreams'


def _invert(d):
  return {v: k for k, v in d.items()}

OBJECT_TYPE_TO_TYPE = {
  'article': 'Article',
  'audio': 'Audio',
  'collection': 'Collection',
  'comment': 'Note',
  'event': 'Event',
  'image': 'Image',
  'note': 'Note',
  'person': 'Person',
  'place': 'Place',
  'video': 'Video',
}
TYPE_TO_OBJECT_TYPE = _invert(OBJECT_TYPE_TO_TYPE)

VERB_TO_TYPE = {
  'favorite': 'Favorite',
  'invite': 'Invite',
  'like': 'Like',
  'post': 'Create',
  'rsvp-maybe': 'TentativeAccept',
  'rsvp-no': 'Reject',
  'rsvp-yes': 'Accept',
  'share': 'Announce',
  'tag': 'Add',
  'update': 'Update',
}
TYPE_TO_VERB = _invert(VERB_TO_TYPE)


def from_as1(obj, type=None, context=CONTEXT):
  """Converts an ActivityStreams 1 activity or object to ActivityStreams 2.

  Args:
    obj: dict, AS1 activity or object/
    type: string, default type if type inference can't determine a type.
    context: string, included as @context

  Returns: dict, AS2 activity or object
  """
  if not obj:
    return {}
  elif not isinstance(obj, dict):
    raise ValueError('Expected dict, got %r' % obj)

  obj = copy.deepcopy(obj)

  verb = obj.pop('verb', None)
  obj_type = obj.pop('objectType', None)
  type = (OBJECT_TYPE_TO_TYPE.get(verb or obj_type) or
          VERB_TO_TYPE.get(verb or obj_type) or
          type)

  if context:
    obj['@context'] = CONTEXT

  def all_from_as1(field, type=None):
    return [from_as1(elem, type=type, context=None)
            for elem in util.pop_list(obj, field)]

  obj.update({
    'type': type,
    'name': obj.pop('displayName', None),
    'actor': from_as1(obj.get('actor'), context=None),
    'attachment': all_from_as1('attachments'),
    'attributedTo': all_from_as1('author', type='Person'),
    'image': all_from_as1('image', type='Image'),
    'inReplyTo': util.trim_nulls([orig.get('url') for orig in obj.get('inReplyTo', [])]),
    'object': from_as1(obj.get('object'), context=None),
    'tag': all_from_as1('tags')
  })

  loc = obj.get('location')
  if loc:
    obj['location'] = from_as1(loc, type='Place', context=None)

  obj = util.trim_nulls(obj)
  if obj.keys() == ['url']:
    return obj['url']

  return obj


def to_as1(obj, use_type=True):
  """Converts an ActivityStreams 2 activity or object to ActivityStreams 1.

  Args:
    obj: dict, AS2 activity or object
    use_type: boolean, whether to include objectType and verb

  Returns: dict, AS1 activity or object
  """
  if not obj:
    return {}
  elif isinstance(obj, basestring):
    return {'url': obj}
  elif not isinstance(obj, dict):
    raise ValueError('Expected dict, got %r' % obj)

  obj = copy.deepcopy(obj)

  obj.pop('@context', None)

  type = obj.pop('type', None)
  if use_type:
    obj['objectType'] = TYPE_TO_OBJECT_TYPE.get(type)
    obj['verb'] = TYPE_TO_VERB.get(type)
    if obj.get('inReplyTo') and obj['objectType'] in ('note', 'article'):
      obj['objectType'] = 'comment'
    elif obj['verb'] and not obj['objectType']:
      obj['objectType'] = 'activity'

  def url_or_as1(val):
    return {'url': val} if isinstance(val, basestring) else to_as1(val)

  def all_to_as1(field):
    return [to_as1(elem) for elem in util.pop_list(obj, field)]

  obj.update({
    'displayName': obj.pop('name', None),
    'actor': to_as1(obj.get('actor')),
    'attachments': all_to_as1('attachment'),
    'image': [to_as1(img, use_type=False) for img in obj.get('image', [])],
    'inReplyTo': [url_or_as1(orig) for orig in util.get_list(obj, 'inReplyTo')],
    'location': url_or_as1(obj.get('location')),
    'object': to_as1(obj.get('object')),
    'tags': all_to_as1('tag'),
  })

  attrib = util.pop_list(obj, 'attributedTo')
  if attrib:
    if len(attrib) > 1:
      logging.warning('ActivityStreams 1 only supports single author; '
                      'dropping extra attributedTo values: %s' % attrib[1:])
    obj['author'] = to_as1(attrib[0])

  return util.trim_nulls(obj)
