import logging
import time
from StringIO import StringIO

try:
    import pygal
except:
    pygal = None

from openerp import api, models, fields

_logger = logging.getLogger(__name__)

class TelegramCommand(models.Model):

    _inherit = "telegram.command"

    @api.multi
    def _get_globals_dict(self):
        res = super(TelegramCommand, self)._get_globals_dict()
        res['pygal'] = pygal
        return res

    @api.multi
    def _eval(self, *args, **kwargs):
        locals_dict = kwargs.get('locals_dict') or {}
        locals_dict['charts'] = []
        kwargs['locals_dict'] = locals_dict
        return super(TelegramCommand, self)._eval(*args, **kwargs)

    def _render(self, template, locals_dict, tsession):
        res = super(TelegramCommand, self)._render(template, locals_dict, tsession)
        t0 = time.time()
        photos = []

        for obj in locals_dict.get('charts', []):
            f = StringIO(obj.render_to_png())
            f.name = 'chart.png'
            photos.append({'file': f})

        render_time = time.time() - t0
        _logger.debug('Render Charts in %.2fs\n locals_dict: %s', render_time, locals_dict)
        res['photos'] += photos
        return res
