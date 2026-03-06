"""修复本地数据库缺失的字段和表"""
import sqlite3

conn = sqlite3.connect('contracts.db')
cur = conn.cursor()

# 检查现有表
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('现有表:', tables)

# contracts 表缺失字段
cur.execute('PRAGMA table_info(contracts)')
existing = [row[1] for row in cur.fetchall()]
contract_cols = {
    'original_filename': 'TEXT',
}
for col, typ in contract_cols.items():
    if col not in existing:
        cur.execute(f'ALTER TABLE contracts ADD COLUMN {col} {typ}')
        print(f'contracts 添加字段: {col}')

# supplements 表缺失字段
if 'supplements' in tables:
    cur.execute('PRAGMA table_info(supplements)')
    existing = [row[1] for row in cur.fetchall()]
    sup_cols = {
        'linked_contract_id': 'INTEGER',
        'file_size': 'INTEGER',
        'original_filename': 'TEXT',
    }
    for col, typ in sup_cols.items():
        if col not in existing:
            cur.execute(f'ALTER TABLE supplements ADD COLUMN {col} {typ}')
            print(f'supplements 添加字段: {col}')

# payments 表缺失字段
if 'payments' in tables:
    cur.execute('PRAGMA table_info(payments)')
    existing = [row[1] for row in cur.fetchall()]
    pay_cols = {
        'payment_theme': 'TEXT',
        'operator': 'TEXT',
        'cost_center': 'TEXT',
        'project_name': 'TEXT',
        'contract_number': 'TEXT',
        'application_number': 'TEXT',
        'payment_reason': 'TEXT',
        'counterparty': 'TEXT',
    }
    for col, typ in pay_cols.items():
        if col not in existing:
            cur.execute(f'ALTER TABLE payments ADD COLUMN {col} {typ}')
            print(f'payments 添加字段: {col}')

# 检查是否缺少 partners / partner_attachments / contract_attachments 表
missing_tables = []
for t in ['partners', 'partner_attachments', 'contract_attachments']:
    if t not in tables:
        missing_tables.append(t)

if missing_tables:
    print(f'缺少表: {missing_tables}，正在创建...')
    if 'partners' not in tables:
        cur.execute('''CREATE TABLE partners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact_name TEXT,
            contact_phone TEXT,
            address TEXT,
            bank_name TEXT,
            bank_account TEXT,
            notes TEXT,
            is_deleted INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        print('创建表: partners')

    if 'partner_attachments' not in tables:
        cur.execute('''CREATE TABLE partner_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_id INTEGER,
            file_name TEXT,
            file_path TEXT,
            file_size INTEGER,
            is_deleted INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        print('创建表: partner_attachments')

    if 'contract_attachments' not in tables:
        cur.execute('''CREATE TABLE contract_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id INTEGER,
            file_name TEXT,
            file_path TEXT,
            file_size INTEGER,
            file_url TEXT,
            attachment_type TEXT DEFAULT "contract",
            is_primary INTEGER DEFAULT 0,
            is_deleted INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        print('创建表: contract_attachments')

conn.commit()
conn.close()
print('数据库修复完成')
