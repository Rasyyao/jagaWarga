from enum import Enum

class IntentLabel(str, Enum):
    LAPORAN_PENIPUAN = "laporan_penipuan"
    LAPORAN_HOAKS = "laporan_hoaks"
    LAPORAN_PENGADUAN_LAYANAN = "laporan_pengaduan_layanan"
    TIDAK_RELEVAN = "tidak_relevan"
    SPAM = "spam"
    
class ReportType(str, Enum):
    PENIPUAN_ONLINE = "penipuan_online"
    PENIPUAN_OFFLINE = "penipuan_offline"
    HOAKS_POLITIK = "hoaks_politik"
    HOAKS_KESEHATAN = "hoaks_kesehatan"
    HOAKS_BENCANA = "hoaks_bencana"
    PENGADUAN_PELAYANAN_PUBLIK = "pengaduan_pelayanan_publik"
    PENGADUAN_INFRASTRUKTUR = "pengaduan_infrastruktur"
    UNKNOWN = "unknown"
    
class InputType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    LINK = "link"
    
class PipelineStatus(str, Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    DROPPED = "dropped"
    CACHE_HIT = "cache_hit"
    COMPLETED = "completed"
    FAILED = "failed"
    
    
