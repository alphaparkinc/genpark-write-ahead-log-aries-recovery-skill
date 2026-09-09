class LogRecord:
    def __init__(self, lsn, tx_id, rec_type, page_id=None, prev_lsn=None, undo_next_lsn=None, before_val=None, after_val=None):
        self.lsn = lsn
        self.tx_id = tx_id
        self.rec_type = rec_type
        self.page_id = page_id
        self.prev_lsn = prev_lsn
        self.undo_next_lsn = undo_next_lsn
        self.before_val = before_val
        self.after_val = after_val

class ARIESRecoveryEngine:
    """Standard ARIES 3-Phase Crash Recovery Algorithm."""
    def __init__(self):
        self.log = []
        self.flushed_lsn = 0
        self.page_table = {}
        self.disk_pages = {}
        self.tx_table = {}
        self.dirty_page_table = {}

    def append_log(self, tx_id, rec_type, page_id=None, prev_lsn=None, undo_next_lsn=None, before_val=None, after_val=None):
        lsn = len(self.log) + 1
        rec = LogRecord(lsn, tx_id, rec_type, page_id, prev_lsn, undo_next_lsn, before_val, after_val)
        self.log.append(rec)
        self.flushed_lsn = lsn
        return lsn

    def begin_tx(self, tx_id):
        lsn = self.append_log(tx_id, 'BEGIN')
        self.tx_table[tx_id] = {'last_lsn': lsn, 'status': 'ACTIVE'}
        return lsn

    def update_page(self, tx_id, page_id, before_val, after_val):
        prev_lsn = self.tx_table[tx_id]['last_lsn']
        lsn = self.append_log(tx_id, 'UPDATE', page_id=page_id, prev_lsn=prev_lsn, before_val=before_val, after_val=after_val)
        self.tx_table[tx_id]['last_lsn'] = lsn
        if page_id not in self.dirty_page_table:
            self.dirty_page_table[page_id] = lsn
        self.page_table[page_id] = {'val': after_val, 'page_lsn': lsn}
        return lsn

    def commit_tx(self, tx_id):
        prev_lsn = self.tx_table[tx_id]['last_lsn']
        lsn = self.append_log(tx_id, 'COMMIT', prev_lsn=prev_lsn)
        self.tx_table[tx_id]['last_lsn'] = lsn
        self.tx_table[tx_id]['status'] = 'COMMITTED'
        return lsn

    def flush_page_to_disk(self, page_id):
        if page_id in self.page_table:
            self.disk_pages[page_id] = dict(self.page_table[page_id])
            if page_id in self.dirty_page_table:
                del self.dirty_page_table[page_id]

    def crash(self):
        self.page_table = {p: dict(v) for p, v in self.disk_pages.items()}
        self.tx_table = {}
        self.dirty_page_table = {}

    def recover(self):
        analysis_tx_table = {}
        analysis_dpt = {}

        for rec in self.log:
            if rec.rec_type == 'BEGIN':
                analysis_tx_table[rec.tx_id] = {'last_lsn': rec.lsn, 'status': 'ACTIVE'}
            elif rec.rec_type == 'UPDATE':
                analysis_tx_table[rec.tx_id] = {'last_lsn': rec.lsn, 'status': 'ACTIVE'}
                if rec.page_id not in analysis_dpt:
                    analysis_dpt[rec.page_id] = rec.lsn
            elif rec.rec_type == 'COMMIT':
                analysis_tx_table[rec.tx_id]['status'] = 'COMMITTED'
            elif rec.rec_type == 'CLR':
                analysis_tx_table[rec.tx_id] = {'last_lsn': rec.lsn, 'status': 'ACTIVE'}
                if rec.page_id not in analysis_dpt:
                    analysis_dpt[rec.page_id] = rec.lsn

        losers = {t for t, info in analysis_tx_table.items() if info['status'] == 'ACTIVE'}
        redo_start_lsn = min(analysis_dpt.values()) if analysis_dpt else (len(self.log) + 1)
        redo_count = 0

        for rec in self.log:
            if rec.lsn >= redo_start_lsn:
                if rec.rec_type in ('UPDATE', 'CLR'):
                    page_disk_lsn = self.page_table.get(rec.page_id, {}).get('page_lsn', 0)
                    if rec.lsn > page_disk_lsn:
                        self.page_table[rec.page_id] = {'val': rec.after_val, 'page_lsn': rec.lsn}
                        redo_count += 1

        to_undo = {t: analysis_tx_table[t]['last_lsn'] for t in losers}
        undo_count = 0

        while any(lsn is not None and lsn > 0 for lsn in to_undo.values()):
            max_lsn = -1
            target_tx = None
            for tx, lsn in to_undo.items():
                if lsn is not None and lsn > max_lsn:
                    max_lsn = lsn
                    target_tx = tx

            if target_tx is None or max_lsn <= 0:
                break

            rec = self.log[max_lsn - 1]
            if rec.rec_type == 'UPDATE':
                clr_lsn = self.append_log(
                    rec.tx_id, 'CLR', page_id=rec.page_id, prev_lsn=to_undo[target_tx],
                    undo_next_lsn=rec.prev_lsn, before_val=rec.after_val, after_val=rec.before_val
                )
                self.page_table[rec.page_id] = {'val': rec.before_val, 'page_lsn': clr_lsn}
                to_undo[target_tx] = rec.prev_lsn
                undo_count += 1
            elif rec.rec_type == 'CLR':
                to_undo[target_tx] = rec.undo_next_lsn
            elif rec.rec_type == 'BEGIN':
                to_undo[target_tx] = None

        return {
            'losers': list(losers),
            'redo_count': redo_count,
            'undo_count': undo_count,
            'final_pages': {p: v['val'] for p, v in self.page_table.items()}
        }
