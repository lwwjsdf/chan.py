import psycopg2

from Common.CEnum import AUTYPE, DATA_FIELD, KL_TYPE
from Common.CTime import CTime
from DataAPI.CommonStockAPI import CCommonStockApi
from KLine.KLine_Unit import CKLine_Unit


class CPgStock(CCommonStockApi):
    """从 stockmind PostgreSQL 读取数据。"""

    def __init__(self, code, k_type=KL_TYPE.K_DAY, begin_date=None, end_date=None, autype=AUTYPE.QFQ):
        super(CPgStock, self).__init__(code, k_type, begin_date, end_date, autype)
        try:
            from stockmind.core.config import DB_CONFIG
            self._conn_params = DB_CONFIG
        except ImportError:
            self._conn_params = {
                "host": "72.62.197.172", "port": 5432,
                "dbname": "digi-agents", "user": "digi", "password": "digi123",
            }

    def SetBasciInfo(self):
        self.name = None
        self.is_stock = True

    @classmethod
    def do_close(cls):
        pass

    def get_kl_data(self):
        if self.k_type == KL_TYPE.K_DAY:
            yield from self._get_daily_kl_data()
        elif self.k_type == KL_TYPE.K_30M:
            yield from self._get_30min_kl_data()
        else:
            raise ValueError(f"CPgStock 目前只支持日线和30分钟线，不支持 {self.k_type}")

    def _get_daily_kl_data(self):
        sql = """
            SELECT trade_date, open, high, low, close, volume, amount, turnover_rate
            FROM stockmind_daily_bars
            WHERE code = %s
        """
        params = [self.code]
        if self.begin_date:
            sql += " AND trade_date >= %s"
            params.append(self.begin_date)
        if self.end_date:
            sql += " AND trade_date <= %s"
            params.append(self.end_date)
        sql += " ORDER BY trade_date ASC"

        with psycopg2.connect(**self._conn_params) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        if not rows:
            raise ValueError(f"CPgStock: no daily data for {self.code} from {self.begin_date or 'begin'}")

        for trade_date, open_, high, low, close, volume, amount, turnover_rate in rows:
            item = {
                DATA_FIELD.FIELD_TIME: CTime(trade_date.year, trade_date.month, trade_date.day, 0, 0),
                DATA_FIELD.FIELD_OPEN: float(open_) if open_ is not None else 0.0,
                DATA_FIELD.FIELD_HIGH: float(high) if high is not None else 0.0,
                DATA_FIELD.FIELD_LOW: float(low) if low is not None else 0.0,
                DATA_FIELD.FIELD_CLOSE: float(close) if close is not None else 0.0,
                DATA_FIELD.FIELD_VOLUME: float(volume) if volume is not None else 0.0,
                DATA_FIELD.FIELD_TURNOVER: float(amount) if amount is not None else 0.0,
                DATA_FIELD.FIELD_TURNRATE: float(turnover_rate) if turnover_rate is not None else 0.0,
            }
            yield CKLine_Unit(item)

    def _get_30min_kl_data(self):
        sql = """
            SELECT dt, open, high, low, close, volume
            FROM stockmind_30min_bars
            WHERE code = %s
        """
        params = [self.code]
        if self.begin_date:
            sql += " AND dt >= %s"
            params.append(self.begin_date)
        if self.end_date:
            sql += " AND dt <= %s"
            params.append(self.end_date)
        sql += " ORDER BY dt ASC"

        with psycopg2.connect(**self._conn_params) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        if not rows:
            raise ValueError(f"CPgStock: no 30min data for {self.code} from {self.begin_date or 'begin'}")

        for dt, open_, high, low, close, volume in rows:
            item = {
                DATA_FIELD.FIELD_TIME: CTime(dt.year, dt.month, dt.day, dt.hour, dt.minute),
                DATA_FIELD.FIELD_OPEN: float(open_) if open_ is not None else 0.0,
                DATA_FIELD.FIELD_HIGH: float(high) if high is not None else 0.0,
                DATA_FIELD.FIELD_LOW: float(low) if low is not None else 0.0,
                DATA_FIELD.FIELD_CLOSE: float(close) if close is not None else 0.0,
                DATA_FIELD.FIELD_VOLUME: float(volume) if volume is not None else 0.0,
                DATA_FIELD.FIELD_TURNOVER: 0.0,
                DATA_FIELD.FIELD_TURNRATE: 0.0,
            }
            yield CKLine_Unit(item)
