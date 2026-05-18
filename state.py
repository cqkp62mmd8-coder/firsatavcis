"""
Global çalışma durumu — tüm modüller buradan okur/yazar.
Admin komutlarıyla runtime'da değiştirilebilir.
"""
durduruldu: bool = False   # True → yeni mesajlar kuyruğa alınmaz
