import uuid
from peewee import *
db = SqliteDatabase('data.db')
from datetime import datetime
from playhouse.migrate import SqliteMigrator, migrate
migrator = SqliteMigrator(db)

class BaseModel(Model):
    class Meta:
        database = db
        
class User(BaseModel):
    userid = IntegerField(primary_key=True)
    step = CharField(max_length=200,null=True)
    
    joined_at = DateTimeField(default = datetime.now())

    is_ban = BooleanField(default=False)
    
    
    
class Group(BaseModel):
    id  = CharField()
    owner = IntegerField()
    status = BooleanField(default = False)
    created_at = DateTimeField(default = datetime.now())
    tag_all = BooleanField(default = False)
    media_tag= BooleanField(default = False)
    text_tag = BooleanField(default = False)
class Media(BaseModel):
    id = UUIDField(primary_key=True,default=uuid.uuid4)
    type = CharField(max_length=200,null=True)  
    name = CharField(max_length=200)  
    msg_id = IntegerField(default = 0)
    channel = CharField(max_length=200,null=True)  
    caption = CharField(max_length=250,null=True) 
    created_at = DateTimeField(default = datetime.now())
    status = BooleanField(default = False)
class Text(BaseModel):
    id = UUIDField(primary_key=True,default=uuid.uuid4)
    name = CharField(null = True)
    
    text = CharField(null = True)
    created_at = DateTimeField(default = datetime.now())
    status = BooleanField(default = False)
    
class Support(BaseModel):
    from_id = IntegerField()
    to_id = IntegerField()
    reply_to = IntegerField()
    message_id = IntegerField()
    answered =  BooleanField(default=False)
  
    

        
        
class Setting(BaseModel):
    key = CharField(null = True)
    value = CharField(null = True)
    
class AntiFlood(BaseModel):
    user_id = IntegerField(default = 5)
    detail = CharField(default = '[]')
    ban_until = IntegerField(default = 2)
    

class PendingSubmission(BaseModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    submitter_id = IntegerField()
    type = CharField(max_length=10)  # 'text' or 'media'
    name = CharField(null=True)
    text = CharField(null=True)
    caption = CharField(max_length=250, null=True)
    temp_chat_id = CharField(max_length=200, null=True)
    temp_msg_id = IntegerField(default=0)
    approved = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.now())


db.create_tables([User,Setting,AntiFlood,Group,Media,Text,Support,PendingSubmission])


