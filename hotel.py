from trytond.model import ModelSQL,ModelView,fields,Unique,Workflow
from trytond.pool import PoolMeta,Pool
from trytond.pyson import Not,Bool,Eval,If,Or

from datetime import datetime as dt
from dateutil.relativedelta import relativedelta

from twilio.rest import Client

class Guest(ModelSQL,ModelView):
    "Hotel Guest"
    __name__ = 'hotel.guest'

    ref = fields.Function(
        fields.Char('Ref'), 'on_change_with_ref')
    
    guest = fields.Many2One("party.party", "Guest",
                            domain=[
                                ('is_person','=',True)
                            ])

    lastname = fields.Function(
        fields.Char('lastname'),
        getter='get_guest_lastname',
        searcher='search_guest_lastname')
    
    is_admitted = fields.Boolean('Admitted')
    age = fields.Function(fields.Integer('Age'),'on_change_with_age')

    gender = fields.Function(fields.Selection([
        (None, ''),
        ('m', 'Male'),
        ('f', 'Female'),
        ('other', 'Other')]
        ,'Gender'),'on_change_with_gender')
    celphone = fields.Function(fields.Char('Celphone'),'on_change_with_celphone')

    def get_rec_name(self,name=None):
        if self.guest.is_person:
            return f'{self.guest.lastname}, {self.guest.name}'
    
    @classmethod
    def default_is_admitted(cls):
        return True
    
    @fields.depends('guest')
    def on_change_with_ref(self,name=None):
        return self.guest.identifiers[0].code if self.guest and self.guest.identifiers else ''
    
    @fields.depends('guest')
    def on_change_with_age(self,name=None):
        if self.guest and self.guest.dob:
            start = dt.strptime(str(self.guest.dob), '%Y-%m-%d')
            end = dt.strptime(str(dt.today().date()), '%Y-%m-%d')
            age = relativedelta(end,start)
            return age.years
        return None
        
    @fields.depends('guest')
    def on_change_with_gender(self,name=None):
        if self.guest:
            return self.guest.gender
        return None
        
    @fields.depends('guest')
    def on_change_with_celphone(self,name=None):
        if self.guest:
            for contact in self.guest.contact_mechanisms:
                if contact.type == 'mobile':
                    return contact.value
        return ''
        
    @classmethod
    def search_guest_lastname(cls,guest,clause):
        res = []
        value = clause[2]
        res.append(('guest.lastname',clause[1],value))
        return res
    
    #Search by the guest name, lastname
    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
                ('guest',) + tuple(clause[1:]),
                ('lastname',) + tuple(clause[1:]),
                ]
    
    @classmethod
    def __setup__(cls):
        super(Guest,cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('name_uniq',Unique(t,t.guest),'The Guest already exists !'),
        ]

class Room(Workflow,ModelSQL,ModelView):
    'Hotel Bed'
    __name__ = 'hotel.room'

    room = fields.Many2One('product.product','Room')
    room_number = fields.Char('Room Number')
    max_guest = fields.Integer('Max Guest')
    type = fields.Selection([
        ('simple','Simple'),
        ('matrimonial','Matrimonial'),
        ('double','Double')
    ],'Room Type',
    sort = False)
    state = fields.Selection([
        ('free','Free'),
        ('disabled','Disabled'),
        ('taken','Taken'),
        ('to_clean','To Clean')],
        'State',
        sort = False,
        readonly=True
        )

    price = fields.Function(fields.Float('Price'),'on_change_with_price')

    def get_rec_name(self,name=None):
        return f'[{self.room_number}] - {self.room.template.name}'
    
    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._transitions.update({
            ('taken','to_clean'),
            ('to_clean','free'),
            ('disabled','free'),
            ('free','disabled'),
        })
        cls._buttons.update({
            'to_clean':{
                'invisible': Eval('state') != 'taken',
            },
            'free':{
                'invisible': Not(Eval('state').in_(['to_clean', 'disabled'])),
            },
            'disabled':{
                'invisible': Eval('state') != 'free',
            },
        })
    
    @classmethod
    def default_state(cls):
        return 'free'

    @classmethod
    @ModelView.button
    @Workflow.transition('to_clean')
    def to_clean(cls,rooms):
        return

    @classmethod
    @ModelView.button
    @Workflow.transition('free')
    def free(cls,rooms):
        return

    @classmethod
    @ModelView.button
    @Workflow.transition('disabled')
    def disabled(cls,rooms):
        return

    @fields.depends('room')
    def on_change_with_price(self,name=None):
        if self.room:
            price = self.room.template.list_prices[0].list_price
            return price
        else:
            return None
        
    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
                ('room',) + tuple(clause[1:]),
                ('room_number',) + tuple(clause[1:]),
                ]

class RoomReservations(Workflow,ModelSQL,ModelView):
    'Hotel Rooms Reservations'
    __name__ = 'hotel.room.reservations'

    room = fields.Many2One('hotel.room','Room',
                           required=True,
                           domain=[
                               ('state','=','free')
                           ],
                           states={
                                'readonly': Eval('state') == 'closed',
                                })
    reserved_by = fields.Many2One('hotel.guest','Reserved by',
                                  required=True,
                                  states={
                                        'readonly': Eval('state') == 'closed',
                                        })
    check_in = fields.DateTime('Check in',
                               readonly=True)
    check_out = fields.DateTime('Check out',
                                readonly=True)
    price = fields.Integer('Price',
                           states={
                                'readonly': Eval('state') != 'draft',
                                })
    observations = fields.Text('Observations',
                               states={
                                   'readonly': Eval('state') == 'closed',
                                   })
    guest = fields.One2Many(
        'hotel.room.reservations.guest',
        'reservation','Guests Line',
        states={
            'readonly': Eval('state') != 'open',
        })
    service = fields.One2Many(
        'hotel.service',
        'reservation','Service',
        readonly=True
        # states={
        #     'readonly': Eval('state') != 'open',
        # }
        )
    state = fields.Selection([
        ('draft','Draft'),
        ('open','Open'),
        ('closed','Closed')
        ],'State',
        sort = False,
        readonly=True)
    total_reservation = fields.Function(fields.Float('Total'), 'get_total_reservation')

    def get_total_reservation(self,name):
        if self.service:
            total = 0
            for service in self.service:
                total = total + service.total
            return total

        return 0

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._transitions.update({
            ('draft','open'),
            ('open','closed'),
        })
        cls._buttons.update({
            'open':{
                'invisible': Eval('state') != 'draft',
            },
            'closed':{
                'invisible': Eval('state') != 'open',
            },
        })
    
    @classmethod
    @ModelView.button
    @Workflow.transition('open')
    def open(cls,reservations):
        pool = Pool()
        Service = pool.get('hotel.service')
        ServiceLine = pool.get('hotel.service.line')
        to_save = []
        to_save_services = []
        to_save_service_lines = []
        for reservation in reservations:
            reservation.room.state = 'taken'
            reservation.room.save()
            print(reservation.room.rec_name)
            print(dt.now())
            cuarto = reservation.room.rec_name
            hora = dt.now().strftime("%Y-%m-%d %H:%M")
            precio = reservation.price

            new_guest = RoomReservationsGuest(
                reservation = reservation,
                guest = reservation.reserved_by,
            )
            to_save.append(new_guest)

            room_product = reservation.room.room
            new_service = Service(
                name = '',
                reservation = reservation,
                total_price = reservation.price,
                state = 'open',
            )
            to_save_services.append(new_service)

            new_service_line = ServiceLine(
                service = new_service,
                product = room_product,
                qty = 1,
                unit_price = reservation.price
            )
            to_save_service_lines.append(new_service_line)

        RoomReservationsGuest.save(to_save)    
        Service.save(to_save_services)
        ServiceLine.save(to_save_service_lines
        )
        cls.write(reservations,{
            'check_in': dt.now(),
        })
    
    @classmethod
    @ModelView.button
    @Workflow.transition('closed')
    def closed(cls,reservations):
        for reservation in reservations:
            reservation.room.state = 'to_clean'
            reservation.room.save()
            reservation.service[0].state = 'closed'
            reservation.service[0].save()
        cls.write(reservations,{
            'check_out':dt.now(),
        })
    
    @classmethod
    def default_state(cls):
        return 'draft'
        
    @fields.depends('room')
    def on_change_with_price(self,name=None):
        if self.room:
            return self.room.price
        
    

class RoomReservationsGuest(ModelSQL,ModelView):
    'Hotel Room Reservations Guest'
    __name__ = 'hotel.room.reservations.guest'
    _rec_name = 'guest'

    reservation = fields.Many2One(
        'hotel.room.reservations','Reservation',
        ondelete='CASCADE',
    )
    guest = fields.Many2One(
        'hotel.guest','Guest')