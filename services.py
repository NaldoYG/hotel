from trytond.model import ModelSQL,ModelView,fields
from trytond.pool import PoolMeta,Pool
from trytond.pyson import Not,Bool,Eval,If

from datetime import datetime as dt
from dateutil.relativedelta import relativedelta
        

class Services(ModelSQL,ModelView):
    'Hotel Service'
    __name__ = 'hotel.service'

    name = fields.Char('Service',readonly=True)
    reservation = fields.Many2One('hotel.room.reservations','Reservation',
                                ondelete='CASCADE',)
    payment = fields.Float('Amount Paid',
                           states={
                               'readonly': Eval('state') == 'closed',
                           })
    refund = fields.Function(fields.Float('Refund'),'on_change_with_refund')
    indebt = fields.Function(fields.Float('Indebt'),'on_change_with_indebt')
    total = fields.Function(fields.Float('Total'),'on_change_with_total')
    total_price = fields.Float('Total')

    service_line = fields.One2Many(
        'hotel.service.line',
        'service','Service Lines',
        states={
            'readonly': Eval('state') == 'closed',
            })
    state = fields.Selection([
        ('draft','Draft'),
        ('open','Open'),
        ('closed','Closed')
    ],'State',
    sort = False,
    readonly=True)

    

    @classmethod
    def default_state(cls):
        return 'draft'

    @fields.depends('payment','total')
    def on_change_with_refund(self,name=None):
        if self.payment and self.total:
            if self.payment > self.total:
                return self.payment - self.total
        return 0

    @fields.depends('total')
    def on_change_with_indebt(self,name=None):
        return 0

    @fields.depends('service_line')
    def on_change_with_total_price(self,name=None):
        total = 0
        if self.service_line:
            for line_instance in self.service_line:
                total = total + line_instance.price
            return total
        
    @fields.depends('service_line')
    def on_change_with_total(self,name=None):
        total = 0
        if self.service_line:
            for line_instance in self.service_line:
                total = total + line_instance.price
            return total
        
    @classmethod
    def create(cls,vlist):
        vlist = [x.copy() for x in vlist]
        for values in vlist:
            values['name'] = 'SRVC-'+ str(values['reservation'])
        return super(Services,cls).create(vlist)

class ServicesLines(ModelSQL,ModelView):
    'Hotel Service Lines'
    __name__ = 'hotel.service.line'

    service = fields.Many2One('hotel.service','Service',
                              ondelete='CASCADE')
    product = fields.Many2One('product.product', 'Product',
                            states={
                            'readonly': Eval('status') == 'closed',
                            })
    qty = fields.Integer('Quantity',
                         states={
                             'readonly': Eval('status') == 'closed',
                         })
    unit_price = fields.Float('Unit Price',
                            states={
                            'readonly': Eval('status') == 'closed',
                         })
    price = fields.Function(fields.Float('Price'),'on_change_with_price')
    status = fields.Function(fields.Char('Status'),'get_state_service')

    @fields.depends('product')
    def on_change_with_unit_price(self,name=None):
        if self.product:
            price = self.product.template.list_price
            return price
        else:
            return None
        
    def get_state_service(self,name):
        if self.product:
            return self.service.state
        return None

    
    @classmethod
    def default_qty(cls):
        return 1
    
    @classmethod
    def default_unit_price(cls):
        return 0
        
    @fields.depends('product','unit_price','qty')
    def on_change_with_price(self,name=None):
        if self.product:
            if self.unit_price != 0:
                return self.qty*self.unit_price
            else:
                self.unit_price = self.product.template.list_price
                return self.qty*self.unit_price
        else:
            return None