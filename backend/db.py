import os
import pyodbc
from contextlib import contextmanager
from queue import Queue, Empty
import threading
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MSSQL_SERVER = os.getenv('MSSQL_SERVER', 'localhost')
MSSQL_DATABASE = os.getenv('MSSQL_DATABASE', 'JobPortal')
MSSQL_USER = os.getenv('MSSQL_USER', 'Test')
MSSQL_PASSWORD = os.getenv('MSSQL_PASSWORD', 'Root@123')
MSSQL_PORT = int(os.getenv('MSSQL_PORT', '1433'))
MSSQL_ODBC_DRIVER = os.getenv('MSSQL_ODBC_DRIVER', '{ODBC Driver 17 for SQL Server}')

# Connection pool configuration
POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '5'))
CONNECTION_TIMEOUT = int(os.getenv('DB_CONNECTION_TIMEOUT', '10'))

connection_string = (
    f'DRIVER={MSSQL_ODBC_DRIVER};'
    f'SERVER={MSSQL_SERVER},{MSSQL_PORT};'
    f'DATABASE={MSSQL_DATABASE};'
    f'UID={MSSQL_USER};'
    f'PWD={MSSQL_PASSWORD};'
    f'TrustServerCertificate=yes;'
    f'Connection Timeout={CONNECTION_TIMEOUT};'
)

# Debug: Print connection info (without password)
print(f"[DB CONFIG] Server: {MSSQL_SERVER}:{MSSQL_PORT}")
print(f"[DB CONFIG] Database: {MSSQL_DATABASE}")
print(f"[DB CONFIG] User: {MSSQL_USER}")
print(f"[DB CONFIG] Driver: {MSSQL_ODBC_DRIVER}")

# Simple connection pool
class ConnectionPool:
    def __init__(self, pool_size=5):
        self.pool_size = pool_size
        self.pool = Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        self._initialized = False
    
    def _create_connection(self):
        """Create a new database connection"""
        try:
            return pyodbc.connect(connection_string, autocommit=False, timeout=CONNECTION_TIMEOUT)
        except Exception as e:
            print(f"[DB ERROR] Failed to create connection: {e}")
            raise
    
    def get_connection(self, timeout=5):
        """Get a connection from the pool"""
        # Lazy initialization
        if not self._initialized:
            with self.lock:
                if not self._initialized:
                    print(f"[DB] Initializing connection pool with {self.pool_size} connections...")
                    for _ in range(self.pool_size):
                        try:
                            conn = self._create_connection()
                            self.pool.put(conn)
                        except Exception as e:
                            print(f"[DB WARNING] Could not pre-populate connection: {e}")
                    self._initialized = True
        
        try:
            # Try to get existing connection
            conn = self.pool.get(timeout=timeout)
            # Test if connection is alive
            try:
                conn.cursor().execute("SELECT 1").fetchone()
                return conn
            except:
                # Connection is dead, create new one
                try:
                    conn.close()
                except:
                    pass
                return self._create_connection()
        except Empty:
            # Pool is empty, create new connection on-demand
            return self._create_connection()
    
    def return_connection(self, conn):
        """Return a connection to the pool"""
        try:
            # Only return if pool not full
            if self.pool.qsize() < self.pool_size:
                self.pool.put_nowait(conn)
            else:
                conn.close()
        except:
            try:
                conn.close()
            except:
                pass

# Global connection pool
_connection_pool = ConnectionPool(pool_size=POOL_SIZE)

@contextmanager
def get_conn():
    """Get a database connection from the pool"""
    conn = None
    try:
        conn = _connection_pool.get_connection()
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            _connection_pool.return_connection(conn)


def rows_to_dicts(cursor, rows):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def db_run(query: str, params: list | tuple = ()):  # returns {lastID, changes}
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        changes = cursor.rowcount if cursor.rowcount is not None else 0
        last_id = None
        # Try to fetch SCOPE_IDENTITY when present
        try:
            more = True
            last_identity = None
            while more:
                try:
                    rows = cursor.fetchall()
                    for r in rows:
                        if hasattr(r, 'lastID'):
                            last_identity = int(r.lastID)
                except pyodbc.ProgrammingError:
                    pass
                more = cursor.nextset()
            last_id = last_identity
        except pyodbc.Error:
            pass
        return {"lastID": last_id, "changes": changes}


def db_get(query: str, params: list | tuple = ()):  # returns single dict or None
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))


def db_all(query: str, params: list | tuple = ()):  # returns list of dicts
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        if not rows:
            return []
        return rows_to_dicts(cursor, rows)


def run_migrations():
    """Run SQL migration files"""
    import os
    migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
    if os.path.exists(migrations_dir):
        migration_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith('.sql')])
        for migration_file in migration_files:
            migration_path = os.path.join(migrations_dir, migration_file)
            with open(migration_path, 'r', encoding='utf-8') as f:
                migration_sql = f.read()
                # Split by GO statements
                statements = [s.strip() for s in migration_sql.split('GO') if s.strip()]
                with get_conn() as conn:
                    cursor = conn.cursor()
                    for stmt in statements:
                        if stmt and not stmt.startswith('PRINT'):
                            try:
                                cursor.execute(stmt)
                            except Exception as e:
                                print(f"Migration warning in {migration_file}: {str(e)}")


def init_db():
    statements = [
        '''
        IF OBJECT_ID('dbo.hr_signup', 'U') IS NULL
        BEGIN
          CREATE TABLE dbo.hr_signup (
            hrid NVARCHAR(20) NOT NULL PRIMARY KEY,
            full_name NVARCHAR(255) NOT NULL,
            email NVARCHAR(255) UNIQUE NOT NULL,
            company NVARCHAR(255) NOT NULL,
            password NVARCHAR(255) NULL,
            created_at DATETIME2 DEFAULT SYSUTCDATETIME()
          );
        END
        ''',
        '''
        IF COL_LENGTH('dbo.candidate_profiles', 'education') IS NOT NULL
        BEGIN
          ALTER TABLE dbo.candidate_profiles DROP COLUMN education;
        END
        IF COL_LENGTH('dbo.candidate_profiles', 'certifications') IS NOT NULL
        BEGIN
          ALTER TABLE dbo.candidate_profiles DROP COLUMN certifications;
        END
        IF COL_LENGTH('dbo.candidate_profiles', 'experiences') IS NOT NULL
        BEGIN
          ALTER TABLE dbo.candidate_profiles DROP COLUMN experiences;
        END
        ''',
        '''
        IF OBJECT_ID('dbo.candidate_signup', 'U') IS NOT NULL
        BEGIN
          IF OBJECT_ID('dbo.candidate_education', 'U') IS NULL
          BEGIN
            CREATE TABLE dbo.candidate_education (
              candidate_id NVARCHAR(20) NOT NULL,
              degree NVARCHAR(255),
              institution NVARCHAR(255),
              [cgpa/percentage] NVARCHAR(50),
              start_date NVARCHAR(50),
              end_date NVARCHAR(50),
              CONSTRAINT FK_candidate_education_signup FOREIGN KEY (candidate_id) REFERENCES dbo.candidate_signup(cid) ON DELETE CASCADE
            );
            CREATE INDEX IX_candidate_education_candidate ON dbo.candidate_education(candidate_id);
          END
        END
        ''',
        '''
        IF OBJECT_ID('dbo.candidate_education', 'U') IS NOT NULL
        BEGIN
          IF COL_LENGTH('dbo.candidate_education', 'cgpa') IS NOT NULL AND COL_LENGTH('dbo.candidate_education', 'cgpa/percentage') IS NULL
          BEGIN
            EXEC sp_rename 'dbo.candidate_education.cgpa', 'cgpa/percentage', 'COLUMN';
          END
        END
        ''',
        '''
        IF OBJECT_ID('dbo.candidate_education', 'U') IS NOT NULL
           AND COL_LENGTH('dbo.candidate_education', 'id') IS NOT NULL
        BEGIN
          DECLARE @pk_candidate_education NVARCHAR(200);
          SELECT @pk_candidate_education = name FROM sys.key_constraints 
          WHERE parent_object_id = OBJECT_ID('dbo.candidate_education') AND type = 'PK';
          IF @pk_candidate_education IS NOT NULL
          BEGIN
            EXEC('ALTER TABLE dbo.candidate_education DROP CONSTRAINT ' + @pk_candidate_education);
          END
          ALTER TABLE dbo.candidate_education DROP COLUMN id;
        END
        ''',
        '''
        IF OBJECT_ID('dbo.candidate_signup', 'U') IS NOT NULL
        BEGIN
          IF OBJECT_ID('dbo.candidate_certifications', 'U') IS NULL
          BEGIN
            CREATE TABLE dbo.candidate_certifications (
              candidate_id NVARCHAR(20) NOT NULL,
              certification NVARCHAR(255),
              issuer NVARCHAR(255),
              end_month NVARCHAR(50),
              CONSTRAINT FK_candidate_certifications_signup FOREIGN KEY (candidate_id) REFERENCES dbo.candidate_signup(cid) ON DELETE CASCADE
            );
            CREATE INDEX IX_candidate_certifications_candidate ON dbo.candidate_certifications(candidate_id);
          END
        END
        ''',
        '''
        IF OBJECT_ID('dbo.candidate_signup', 'U') IS NOT NULL
        BEGIN
          IF OBJECT_ID('dbo.candidate_experiences', 'U') IS NULL
          BEGIN
            CREATE TABLE dbo.candidate_experiences (
              candidate_id NVARCHAR(20) NOT NULL,
              company NVARCHAR(255),
              role NVARCHAR(255),
              start_date NVARCHAR(50),
              end_date NVARCHAR(50),
              present NVARCHAR(10),
              CONSTRAINT FK_candidate_experiences_signup FOREIGN KEY (candidate_id) REFERENCES dbo.candidate_signup(cid) ON DELETE CASCADE
            );
            CREATE INDEX IX_candidate_experiences_candidate ON dbo.candidate_experiences(candidate_id);
          END
        END
        ''',
        '''
        IF OBJECT_ID('dbo.candidate_experiences', 'U') IS NOT NULL
        BEGIN
          IF COL_LENGTH('dbo.candidate_experiences', 'present_date') IS NOT NULL AND COL_LENGTH('dbo.candidate_experiences', 'present') IS NULL
          BEGIN
            EXEC sp_rename 'dbo.candidate_experiences.present_date', 'present', 'COLUMN';
            -- Convert existing data: if present had a value (date), set to 'yes', otherwise 'no'
            UPDATE dbo.candidate_experiences SET present = CASE WHEN present IS NOT NULL AND present != '' THEN 'yes' ELSE 'no' END;
          END
          IF COL_LENGTH('dbo.candidate_experiences', 'present') IS NULL
          BEGIN
            ALTER TABLE dbo.candidate_experiences ADD present NVARCHAR(10) NULL;
            -- Set default value for new column
            UPDATE dbo.candidate_experiences SET present = 'no' WHERE present IS NULL;
          END
        END
        ''',
        '''
        IF COL_LENGTH('dbo.hr_signup', 'password') IS NULL
        BEGIN
          ALTER TABLE dbo.hr_signup ADD password NVARCHAR(255) NULL;
        END
        ''',
        '''
        IF COL_LENGTH('dbo.hr_signup', 'hrid') IS NULL
        BEGIN
          ALTER TABLE dbo.hr_signup ADD hrid NVARCHAR(20) NULL;
        END
        ''',
        '''
        IF NOT EXISTS (
          SELECT name FROM sys.indexes WHERE name = 'UQ_hr_signup_hrid' AND object_id = OBJECT_ID('dbo.hr_signup')
        )
        BEGIN
          CREATE UNIQUE INDEX UQ_hr_signup_hrid ON dbo.hr_signup(hrid) WHERE hrid IS NOT NULL;
        END
        ''',
        '''
        IF COL_LENGTH('dbo.hr_signup','id') IS NOT NULL
        BEGIN
          EXEC('UPDATE s SET hrid = RIGHT(''HRID'' + RIGHT(''000'' + CAST(s.id AS VARCHAR(10)), 3), 7)
                FROM dbo.hr_signup s
                WHERE s.hrid IS NULL;');
        END
        ''',
        # Intentionally moved drop-id step to after jobs migration
        '''
        IF OBJECT_ID('dbo.hr_login', 'U') IS NULL
        BEGIN
          CREATE TABLE dbo.hr_login (
            hrid NVARCHAR(20) NOT NULL,
            email NVARCHAR(255) NOT NULL,
            password NVARCHAR(255) NOT NULL,
            logged_in_at DATETIME2 DEFAULT SYSUTCDATETIME(),
            CONSTRAINT FK_hr_login_signup_hrid FOREIGN KEY (hrid) REFERENCES dbo.hr_signup(hrid) ON DELETE CASCADE
          );
          CREATE INDEX IX_hr_login_hrid ON dbo.hr_login(hrid);
        END
        ''',
        '''
        -- Migration: add hrid to hr_login if missing and backfill, then drop id
        IF COL_LENGTH('dbo.hr_login', 'hrid') IS NULL
        BEGIN
          ALTER TABLE dbo.hr_login ADD hrid NVARCHAR(20) NULL;
          UPDATE hl SET hrid = hs.hrid FROM dbo.hr_login hl JOIN dbo.hr_signup hs ON hl.email = hs.email;
          ALTER TABLE dbo.hr_login ADD CONSTRAINT FK_hr_login_signup_hrid FOREIGN KEY (hrid) REFERENCES dbo.hr_signup(hrid) ON DELETE CASCADE;
          CREATE INDEX IX_hr_login_hrid ON dbo.hr_login(hrid);
          ALTER TABLE dbo.hr_login ALTER COLUMN hrid NVARCHAR(20) NOT NULL;
          -- Drop old FK and id column if exists
          DECLARE @fk NVARCHAR(200);
          SELECT @fk = name FROM sys.foreign_keys WHERE parent_object_id = OBJECT_ID('dbo.hr_login') AND referenced_object_id = OBJECT_ID('dbo.hr_signup');
          IF @fk IS NOT NULL BEGIN EXEC('ALTER TABLE dbo.hr_login DROP CONSTRAINT ' + @fk); END;
          IF COL_LENGTH('dbo.hr_login','id') IS NOT NULL BEGIN ALTER TABLE dbo.hr_login DROP COLUMN id; END;
        END
        ''',
        '''
        -- Migration: convert hr_login to history table (remove unique constraints, rename created_at to logged_in_at)
        IF OBJECT_ID('dbo.hr_login', 'U') IS NOT NULL
           AND (
             COL_LENGTH('dbo.hr_login', 'logged_in_at') IS NULL OR
             EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UQ_hr_login_hrid' AND object_id = OBJECT_ID('dbo.hr_login')) OR
             EXISTS (SELECT 1 FROM sys.indexes WHERE name LIKE 'UQ_hr_login_email%' AND object_id = OBJECT_ID('dbo.hr_login'))
           )
        BEGIN
          -- Drop unique constraints/indexes
          IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UQ_hr_login_hrid' AND object_id = OBJECT_ID('dbo.hr_login'))
          BEGIN
            DROP INDEX UQ_hr_login_hrid ON dbo.hr_login;
          END
          DECLARE @uq_email_name NVARCHAR(200);
          SELECT @uq_email_name = name FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.hr_login') AND is_unique = 1 AND name LIKE '%email%';
          IF @uq_email_name IS NOT NULL
          BEGIN
            EXEC('DROP INDEX ' + @uq_email_name + ' ON dbo.hr_login');
          END
          
          -- Rename created_at to logged_in_at if needed
          IF COL_LENGTH('dbo.hr_login', 'created_at') IS NOT NULL AND COL_LENGTH('dbo.hr_login', 'logged_in_at') IS NULL
          BEGIN
            EXEC sp_rename 'dbo.hr_login.created_at', 'logged_in_at', 'COLUMN';
          END
          
          -- Create non-unique index on hrid
          IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_hr_login_hrid' AND object_id = OBJECT_ID('dbo.hr_login'))
          BEGIN
            CREATE INDEX IX_hr_login_hrid ON dbo.hr_login(hrid);
          END
        END
        ''',
        '''
        IF NOT EXISTS (
          SELECT 1 FROM sys.sequences 
          WHERE name = 'candidate_cid_seq' AND SCHEMA_NAME(schema_id) = 'dbo'
        )
        BEGIN
          CREATE SEQUENCE dbo.candidate_cid_seq AS INT START WITH 1 INCREMENT BY 1;
        END
        ''',
        '''
        IF OBJECT_ID('dbo.candidate_signup', 'U') IS NULL
        BEGIN
          CREATE TABLE dbo.candidate_signup (
            cid NVARCHAR(20) NOT NULL PRIMARY KEY
              CONSTRAINT DF_candidate_signup_cid DEFAULT ('CID' + FORMAT(NEXT VALUE FOR dbo.candidate_cid_seq, '000')),
            name NVARCHAR(255) NOT NULL,
            email NVARCHAR(255) UNIQUE NOT NULL,
            password NVARCHAR(255) NULL,
            created_at DATETIME2 DEFAULT SYSUTCDATETIME()
          );
        END
        ''',
        '''
        IF COL_LENGTH('dbo.candidate_signup', 'password') IS NULL
        BEGIN
          ALTER TABLE dbo.candidate_signup ADD password NVARCHAR(255) NULL;
        END
        ''',
        '''
        -- Migration: rename candidate_signup.id to cid
        IF COL_LENGTH('dbo.candidate_signup', 'id') IS NOT NULL AND COL_LENGTH('dbo.candidate_signup', 'cid') IS NULL
        BEGIN
          EXEC sp_rename 'dbo.candidate_signup.id', 'cid', 'COLUMN';
        END
        ''',
        '''
        -- Migration: convert candidate_signup.cid to formatted NVARCHAR values (CID001, etc.)
        IF OBJECT_ID('dbo.candidate_signup', 'U') IS NOT NULL
           AND (SELECT system_type_id FROM sys.columns WHERE object_id = OBJECT_ID('dbo.candidate_signup') AND name = 'cid') IN (56, 127, 52)
        BEGIN
          IF COL_LENGTH('dbo.candidate_signup', 'cid_alpha') IS NULL
          BEGIN
            ALTER TABLE dbo.candidate_signup ADD cid_alpha NVARCHAR(20) NULL;
          END
          IF COL_LENGTH('dbo.candidate_signup', 'cid_alpha') IS NOT NULL
          BEGIN
            EXEC('UPDATE dbo.candidate_signup
                  SET cid_alpha = ''CID'' + FORMAT(cid, ''000'')
                  WHERE cid_alpha IS NULL;');
          END
          DECLARE @pk_candidate_signup NVARCHAR(200);
          SELECT @pk_candidate_signup = name FROM sys.key_constraints 
          WHERE parent_object_id = OBJECT_ID('dbo.candidate_signup') AND type = 'PK';
          IF @pk_candidate_signup IS NOT NULL
          BEGIN
            EXEC('ALTER TABLE dbo.candidate_signup DROP CONSTRAINT ' + @pk_candidate_signup);
          END

          DECLARE @df_candidate_cid NVARCHAR(200);
          SELECT @df_candidate_cid = dc.name
          FROM sys.default_constraints dc
          JOIN sys.columns c ON c.default_object_id = dc.object_id
          WHERE dc.parent_object_id = OBJECT_ID('dbo.candidate_signup') AND c.name = 'cid';
          IF @df_candidate_cid IS NOT NULL
          BEGIN
            EXEC('ALTER TABLE dbo.candidate_signup DROP CONSTRAINT ' + @df_candidate_cid);
          END

          ALTER TABLE dbo.candidate_signup DROP COLUMN cid;
          EXEC sp_rename 'dbo.candidate_signup.cid_alpha', 'cid', 'COLUMN';
          ALTER TABLE dbo.candidate_signup ALTER COLUMN cid NVARCHAR(20) NOT NULL;
          ALTER TABLE dbo.candidate_signup ADD CONSTRAINT PK_candidate_signup PRIMARY KEY (cid);
        END
        ''',
        '''
        -- Ensure candidate_signup.cid has default generated from sequence
        IF OBJECT_ID('dbo.candidate_signup', 'U') IS NOT NULL
        BEGIN
          DECLARE @df_candidate_cid2 NVARCHAR(200);
          SELECT @df_candidate_cid2 = dc.name
          FROM sys.default_constraints dc
          JOIN sys.columns c ON c.default_object_id = dc.object_id
          WHERE dc.parent_object_id = OBJECT_ID('dbo.candidate_signup') AND c.name = 'cid';
          IF @df_candidate_cid2 IS NULL
          BEGIN
            ALTER TABLE dbo.candidate_signup ADD CONSTRAINT DF_candidate_signup_cid DEFAULT ('CID' + FORMAT(NEXT VALUE FOR dbo.candidate_cid_seq, '000')) FOR cid;
          END
        END
        ''',
        '''
        -- Align candidate CID sequence with existing max value
        IF OBJECT_ID('dbo.candidate_signup', 'U') IS NOT NULL
        BEGIN
          DECLARE @max_cid_seq INT = (
            SELECT MAX(CAST(SUBSTRING(cid, PATINDEX('%[0-9]%', cid), LEN(cid)) AS INT))
            FROM dbo.candidate_signup
            WHERE PATINDEX('%[0-9]%', cid) > 0
          );
          IF @max_cid_seq IS NOT NULL
          BEGIN
            DECLARE @seq_sql NVARCHAR(200) = 'ALTER SEQUENCE dbo.candidate_cid_seq RESTART WITH ' + CAST(@max_cid_seq + 1 AS NVARCHAR(20));
            EXEC(@seq_sql);
          END
        END
        ''',
        '''
        IF OBJECT_ID('dbo.candidate_login', 'U') IS NULL
        BEGIN
          CREATE TABLE dbo.candidate_login (
            cid NVARCHAR(20) NOT NULL,
            email NVARCHAR(255) NOT NULL,
            password NVARCHAR(255) NOT NULL,
            logged_in_at DATETIME2 DEFAULT SYSUTCDATETIME(),
            CONSTRAINT FK_candidate_login_signup FOREIGN KEY (cid) REFERENCES dbo.candidate_signup(cid) ON DELETE CASCADE
          );
          CREATE INDEX IX_candidate_login_cid ON dbo.candidate_login(cid);
        END
        ''',
        '''
        -- Migration: rename candidate_login.id to cid and update FK
        IF COL_LENGTH('dbo.candidate_login', 'id') IS NOT NULL AND COL_LENGTH('dbo.candidate_login', 'cid') IS NULL
        BEGIN
          -- Drop old FK constraint
          DECLARE @fk_candidate_login NVARCHAR(200);
          SELECT @fk_candidate_login = name FROM sys.foreign_keys WHERE parent_object_id = OBJECT_ID('dbo.candidate_login') AND referenced_object_id = OBJECT_ID('dbo.candidate_signup');
          IF @fk_candidate_login IS NOT NULL BEGIN EXEC('ALTER TABLE dbo.candidate_login DROP CONSTRAINT ' + @fk_candidate_login); END;
          -- Rename column
          EXEC sp_rename 'dbo.candidate_login.id', 'cid', 'COLUMN';
          -- Recreate FK with new column name
          ALTER TABLE dbo.candidate_login ADD CONSTRAINT FK_candidate_login_signup FOREIGN KEY (cid) REFERENCES dbo.candidate_signup(cid) ON DELETE CASCADE;
        END
        ''',
        '''
        -- Migration: rebuild candidate_login to support multiple entries per candidate with logged_in_at and remove login_id
        IF OBJECT_ID('dbo.candidate_login', 'U') IS NOT NULL
           AND (
             COL_LENGTH('dbo.candidate_login', 'login_id') IS NOT NULL OR
             COL_LENGTH('dbo.candidate_login', 'logged_in_at') IS NULL OR
             (SELECT system_type_id FROM sys.columns WHERE object_id = OBJECT_ID('dbo.candidate_login') AND name = 'cid') IN (56, 127, 52)
           )
        BEGIN
          IF OBJECT_ID('dbo.candidate_login_new', 'U') IS NOT NULL DROP TABLE dbo.candidate_login_new;
          CREATE TABLE dbo.candidate_login_new (
            cid NVARCHAR(20) NOT NULL,
            email NVARCHAR(255) NOT NULL,
            password NVARCHAR(255) NOT NULL,
            logged_in_at DATETIME2 DEFAULT SYSUTCDATETIME(),
            CONSTRAINT FK_candidate_login_signup_new FOREIGN KEY (cid) REFERENCES dbo.candidate_signup(cid) ON DELETE CASCADE
          );

          DECLARE @has_created_at BIT = CASE WHEN COL_LENGTH('dbo.candidate_login', 'created_at') IS NOT NULL THEN 1 ELSE 0 END;
          DECLARE @insert_sql NVARCHAR(MAX);
          IF @has_created_at = 1
          BEGIN
            SET @insert_sql = N'
              INSERT INTO dbo.candidate_login_new (cid, email, password, logged_in_at)
              SELECT
                CASE 
                  WHEN TRY_CONVERT(INT, cid) IS NOT NULL AND LEFT(CONVERT(NVARCHAR(20), cid), 3) <> ''CID''
                    THEN ''CID'' + FORMAT(TRY_CONVERT(INT, cid), ''000'')
                  ELSE CONVERT(NVARCHAR(20), cid)
                END,
                email,
                password,
                created_at
              FROM dbo.candidate_login;';
          END
          ELSE
          BEGIN
            SET @insert_sql = N'
              INSERT INTO dbo.candidate_login_new (cid, email, password, logged_in_at)
              SELECT
                CASE 
                  WHEN TRY_CONVERT(INT, cid) IS NOT NULL AND LEFT(CONVERT(NVARCHAR(20), cid), 3) <> ''CID''
                    THEN ''CID'' + FORMAT(TRY_CONVERT(INT, cid), ''000'')
                  ELSE CONVERT(NVARCHAR(20), cid)
                END,
                email,
                password,
                SYSUTCDATETIME()
              FROM dbo.candidate_login;';
          END
          EXEC sp_executesql @insert_sql;

          DROP TABLE dbo.candidate_login;
          EXEC sp_rename 'dbo.candidate_login_new', 'candidate_login';
          CREATE INDEX IX_candidate_login_cid ON dbo.candidate_login(cid);
        END
        ''',
        '''
        IF OBJECT_ID('dbo.jobs', 'U') IS NULL
        BEGIN
          CREATE TABLE dbo.jobs (
            jdid NVARCHAR(20) NOT NULL PRIMARY KEY,
            title NVARCHAR(255) NOT NULL,
            company NVARCHAR(255) NOT NULL,
            location NVARCHAR(255) NOT NULL,
            salary NVARCHAR(255),
            experience NVARCHAR(100),
            description NVARCHAR(MAX) NOT NULL,
            enabled BIT DEFAULT 1,
            posted_by NVARCHAR(20) NULL,
            posted_on DATETIME2 DEFAULT SYSUTCDATETIME(),
            CONSTRAINT FK_jobs_hr_signup_hrid FOREIGN KEY (posted_by) REFERENCES dbo.hr_signup(hrid)
          );
        END
        ''',
        '''
        -- Migration: convert jdid from INT IDENTITY to NVARCHAR(20) based on title
        -- Cleanup: If jdid_new exists from a failed migration, drop it
        IF OBJECT_ID('dbo.jobs', 'U') IS NOT NULL AND COL_LENGTH('dbo.jobs', 'jdid_new') IS NOT NULL
        BEGIN
          ALTER TABLE dbo.jobs DROP COLUMN jdid_new;
        END
        
        -- Run migration only if jdid is INT/numeric (not already NVARCHAR)
        IF OBJECT_ID('dbo.jobs', 'U') IS NOT NULL AND
           COL_LENGTH('dbo.jobs', 'jdid') IS NOT NULL AND
           (SELECT system_type_id FROM sys.columns WHERE object_id = OBJECT_ID('dbo.jobs') AND name = 'jdid') IN (56,127,52)
        BEGIN
          -- jdid is currently INT or numeric type, need to convert to NVARCHAR based on title
          
          -- Step 1: Create a temporary table to store old_id -> new_jdid mapping
          IF OBJECT_ID('tempdb..#jdid_mapping', 'U') IS NOT NULL DROP TABLE #jdid_mapping;
          
          SELECT 
            CAST(jdid AS INT) AS old_id,
            -- Generate jdid from title: first letter of each word + sequence
            CASE 
              WHEN CHARINDEX(' ', title) > 0 THEN
                UPPER(SUBSTRING(title, 1, 1) + 
                  CASE WHEN CHARINDEX(' ', title) > 0 THEN SUBSTRING(title, CHARINDEX(' ', title) + 1, 1) ELSE '' END +
                  CASE WHEN CHARINDEX(' ', title, CHARINDEX(' ', title) + 1) > 0 
                    THEN SUBSTRING(title, CHARINDEX(' ', title, CHARINDEX(' ', title) + 1) + 1, 1) 
                    ELSE '' END
                ) + 
                RIGHT('000' + CAST(ROW_NUMBER() OVER (
                  PARTITION BY 
                    UPPER(SUBSTRING(title, 1, 1) + 
                      CASE WHEN CHARINDEX(' ', title) > 0 THEN SUBSTRING(title, CHARINDEX(' ', title) + 1, 1) ELSE '' END)
                  ORDER BY jdid
                ) AS VARCHAR(10)), 3)
              ELSE
                UPPER(SUBSTRING(title, 1, 2)) + 
                RIGHT('000' + CAST(ROW_NUMBER() OVER (
                  PARTITION BY UPPER(SUBSTRING(title, 1, 2))
                  ORDER BY jdid
                ) AS VARCHAR(10)), 3)
            END AS new_jdid
          INTO #jdid_mapping
          FROM dbo.jobs;
          
          -- Fallback for any that might be NULL
          UPDATE #jdid_mapping SET new_jdid = 'JD' + RIGHT('000' + CAST(ROW_NUMBER() OVER (ORDER BY old_id) AS VARCHAR(10)), 3)
          WHERE new_jdid IS NULL OR LEN(new_jdid) < 3;
          
          -- Step 2: Drop all foreign key constraints referencing jdid
          DECLARE @fk_name_jobs NVARCHAR(200);
          DECLARE @drop_fk_sql NVARCHAR(500);
          DECLARE fk_cur CURSOR FOR
          SELECT name FROM sys.foreign_keys 
          WHERE referenced_object_id = OBJECT_ID('dbo.jobs');
          
          OPEN fk_cur;
          FETCH NEXT FROM fk_cur INTO @fk_name_jobs;
          WHILE @@FETCH_STATUS = 0
          BEGIN
            DECLARE @fk_table NVARCHAR(200);
            SELECT @fk_table = OBJECT_NAME(parent_object_id) FROM sys.foreign_keys WHERE name = @fk_name_jobs;
            SET @drop_fk_sql = 'ALTER TABLE ' + @fk_table + ' DROP CONSTRAINT ' + @fk_name_jobs;
            EXEC sp_executesql @drop_fk_sql;
            FETCH NEXT FROM fk_cur INTO @fk_name_jobs;
          END;
          CLOSE fk_cur;
          DEALLOCATE fk_cur;
          
          -- Step 3: Update foreign key columns with new jdid values
          IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.applications') AND name = 'job_id')
          BEGIN
            UPDATE a SET job_id = CAST(m.new_jdid AS NVARCHAR(20))
            FROM dbo.applications a
            INNER JOIN #jdid_mapping m ON CAST(a.job_id AS INT) = m.old_id;
            
            IF (SELECT system_type_id FROM sys.columns WHERE object_id = OBJECT_ID('dbo.applications') AND name = 'job_id') IN (56,127,52)
            BEGIN
              ALTER TABLE dbo.applications ALTER COLUMN job_id NVARCHAR(20) NOT NULL;
            END
          END
          
          
          -- Step 4: Drop primary key and convert jdid column
          DECLARE @pk_jobs_name NVARCHAR(200);
          SELECT @pk_jobs_name = name FROM sys.key_constraints 
          WHERE parent_object_id = OBJECT_ID('dbo.jobs') AND type = 'PK';
          IF @pk_jobs_name IS NOT NULL
          BEGIN
            EXEC('ALTER TABLE dbo.jobs DROP CONSTRAINT ' + @pk_jobs_name);
          END
          
          -- Check if jdid is IDENTITY and handle accordingly
          DECLARE @is_identity BIT = 0;
          SELECT @is_identity = CASE WHEN is_identity = 1 THEN 1 ELSE 0 END
          FROM sys.columns 
          WHERE object_id = OBJECT_ID('dbo.jobs') AND name = 'jdid';
          
          IF @is_identity = 1
          BEGIN
            -- For IDENTITY columns, we need to add a temporary column, migrate data, then drop old and rename
            -- This temporary column will be immediately renamed to jdid, so no jdid_new remains
            -- Add temporary jdid column as NVARCHAR (only exists during migration)
            IF COL_LENGTH('dbo.jobs', 'jdid_new') IS NULL
            BEGIN
              ALTER TABLE dbo.jobs ADD jdid_new NVARCHAR(20) NULL;
            END
            
            -- Populate temporary column from mapping
            UPDATE j SET jdid_new = m.new_jdid
            FROM dbo.jobs j
            INNER JOIN #jdid_mapping m ON CAST(j.jdid AS INT) = m.old_id;
            
            -- Make temporary column NOT NULL
            ALTER TABLE dbo.jobs ALTER COLUMN jdid_new NVARCHAR(20) NOT NULL;
            
            -- Drop old INT jdid column
            ALTER TABLE dbo.jobs DROP COLUMN jdid;
            
            -- Rename temporary column to jdid (now jdid_new no longer exists, only jdid remains)
            EXEC sp_rename 'dbo.jobs.jdid_new', 'jdid', 'COLUMN';
          END
          ELSE
          BEGIN
            -- For non-IDENTITY columns, we can update directly
            UPDATE j SET jdid = CAST(m.new_jdid AS NVARCHAR(20))
            FROM dbo.jobs j
            INNER JOIN #jdid_mapping m ON CAST(j.jdid AS INT) = m.old_id;
            
            -- Convert column type from INT to NVARCHAR
            ALTER TABLE dbo.jobs ALTER COLUMN jdid NVARCHAR(20) NOT NULL;
          END
          
          -- Recreate primary key
          ALTER TABLE dbo.jobs ADD CONSTRAINT PK_jobs_jdid PRIMARY KEY (jdid);
          
          -- Step 5: Recreate foreign keys
          IF EXISTS (SELECT 1 FROM sys.tables WHERE name = 'applications')
          BEGIN
            IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_applications_job')
            BEGIN
              ALTER TABLE dbo.applications ADD CONSTRAINT FK_applications_job 
                FOREIGN KEY (job_id) REFERENCES dbo.jobs(jdid);
            END
          END
          
          
          -- Clean up temp table
          DROP TABLE #jdid_mapping;
        END
        ''',
        '''
        -- Migration: switch jobs.posted_by to HRID
        IF COL_LENGTH('dbo.jobs','posted_by') IS NOT NULL AND
           (SELECT system_type_id FROM sys.columns WHERE object_id = OBJECT_ID('dbo.jobs') AND name = 'posted_by') IN (56,127)
        BEGIN
          -- posted_by currently numeric; create temp column and backfill
          IF COL_LENGTH('dbo.jobs','posted_by_hrid') IS NULL BEGIN ALTER TABLE dbo.jobs ADD posted_by_hrid NVARCHAR(20) NULL; END;
          IF COL_LENGTH('dbo.hr_signup','id') IS NOT NULL
          BEGIN
            EXEC('UPDATE j SET posted_by_hrid = hs.hrid FROM dbo.jobs j LEFT JOIN dbo.hr_signup hs ON j.posted_by = hs.id');
          END
          -- Drop old FK
          DECLARE @fk2 NVARCHAR(200);
          SELECT @fk2 = name FROM sys.foreign_keys WHERE parent_object_id = OBJECT_ID('dbo.jobs') AND referenced_object_id = OBJECT_ID('dbo.hr_signup');
          IF @fk2 IS NOT NULL BEGIN EXEC('ALTER TABLE dbo.jobs DROP CONSTRAINT ' + @fk2); END;
          ALTER TABLE dbo.jobs DROP COLUMN posted_by;
          EXEC sp_rename 'dbo.jobs.posted_by_hrid', 'posted_by', 'COLUMN';
          ALTER TABLE dbo.jobs ADD CONSTRAINT FK_jobs_hr_signup_hrid FOREIGN KEY (posted_by) REFERENCES dbo.hr_signup(hrid);
        END
        ''',
        '''
        -- Migration: rename jobs.id to jdid (only if jdid is still INT)
        IF COL_LENGTH('dbo.jobs', 'id') IS NOT NULL AND COL_LENGTH('dbo.jobs', 'jdid') IS NULL AND
           (SELECT system_type_id FROM sys.columns WHERE object_id = OBJECT_ID('dbo.jobs') AND name = 'id') IN (56,127,52)
        BEGIN
          EXEC sp_rename 'dbo.jobs.id', 'jdid', 'COLUMN';
        END
        ''',
        '''
        -- Migration: combine experience_from and experience_to into experience column
        IF OBJECT_ID('dbo.jobs', 'U') IS NOT NULL
        BEGIN
          -- Add experience column if it doesn't exist
          IF COL_LENGTH('dbo.jobs', 'experience') IS NULL
          BEGIN
            ALTER TABLE dbo.jobs ADD experience NVARCHAR(100) NULL;
          END
          -- Migrate existing data: combine experience_from and experience_to
          IF COL_LENGTH('dbo.jobs', 'experience_from') IS NOT NULL AND COL_LENGTH('dbo.jobs', 'experience_to') IS NOT NULL
          BEGIN
            EXEC('UPDATE dbo.jobs SET experience = CASE WHEN experience_from IS NOT NULL AND experience_to IS NOT NULL THEN CAST(experience_from AS NVARCHAR(10)) + ''-'' + CAST(experience_to AS NVARCHAR(10)) + '' years'' WHEN experience_from IS NOT NULL AND experience_to IS NULL THEN CAST(experience_from AS NVARCHAR(10)) + ''+ years'' WHEN experience_from IS NULL AND experience_to IS NOT NULL THEN ''Up to '' + CAST(experience_to AS NVARCHAR(10)) + '' years'' ELSE NULL END WHERE experience IS NULL AND (experience_from IS NOT NULL OR experience_to IS NOT NULL)');
          END
          ELSE IF COL_LENGTH('dbo.jobs', 'experience_from') IS NOT NULL
          BEGIN
            EXEC('UPDATE dbo.jobs SET experience = CAST(experience_from AS NVARCHAR(10)) + ''+ years'' WHERE experience IS NULL AND experience_from IS NOT NULL');
          END
          ELSE IF COL_LENGTH('dbo.jobs', 'experience_to') IS NOT NULL
          BEGIN
            EXEC('UPDATE dbo.jobs SET experience = ''Up to '' + CAST(experience_to AS NVARCHAR(10)) + '' years'' WHERE experience IS NULL AND experience_to IS NOT NULL');
          END
          -- Drop old columns
          IF COL_LENGTH('dbo.jobs', 'experience_from') IS NOT NULL BEGIN ALTER TABLE dbo.jobs DROP COLUMN experience_from; END;
          IF COL_LENGTH('dbo.jobs', 'experience_to') IS NOT NULL BEGIN ALTER TABLE dbo.jobs DROP COLUMN experience_to; END;
        END
        ''',
        '''
        IF OBJECT_ID('dbo.candidate_profiles', 'U') IS NULL
        BEGIN
          CREATE TABLE dbo.candidate_profiles (
            candidate_id NVARCHAR(20) PRIMARY KEY NOT NULL,
            full_name NVARCHAR(255),
            email NVARCHAR(255),
            phone NVARCHAR(50),
            experience_level NVARCHAR(50),
            serving_notice NVARCHAR(10),
            notice_period NVARCHAR(50),
            last_working_day NVARCHAR(50),
            linkedin_url NVARCHAR(500),
            portfolio_url NVARCHAR(500),
            current_location NVARCHAR(255),
            preferred_location NVARCHAR(255),
            resume VARBINARY(MAX),
            completed BIT DEFAULT 0,
            updated_at DATETIME2 DEFAULT SYSUTCDATETIME(),
            CONSTRAINT FK_candidate_profiles_signup FOREIGN KEY (candidate_id) REFERENCES dbo.candidate_signup(cid)
          );
        END
        ''',
        '''
        IF OBJECT_ID('dbo.candidate_profiles', 'U') IS NOT NULL
        BEGIN
          -- Remove id column if it exists and make candidate_id the primary key
          IF COL_LENGTH('dbo.candidate_profiles', 'id') IS NOT NULL
          BEGIN
            -- Drop primary key constraint if it exists on id
            DECLARE @pk_candidate_profiles NVARCHAR(200);
            SELECT @pk_candidate_profiles = name FROM sys.key_constraints 
            WHERE parent_object_id = OBJECT_ID('dbo.candidate_profiles') AND type = 'PK';
            IF @pk_candidate_profiles IS NOT NULL
            BEGIN
              EXEC('ALTER TABLE dbo.candidate_profiles DROP CONSTRAINT ' + @pk_candidate_profiles);
            END
            -- Drop the id column
            ALTER TABLE dbo.candidate_profiles DROP COLUMN id;
            -- Make candidate_id the primary key if it's not already
            IF NOT EXISTS (
              SELECT 1 FROM sys.key_constraints 
              WHERE parent_object_id = OBJECT_ID('dbo.candidate_profiles') 
              AND type = 'PK'
            )
            BEGIN
              ALTER TABLE dbo.candidate_profiles ADD CONSTRAINT PK_candidate_profiles PRIMARY KEY (candidate_id);
            END
          END
        END
        ''',
        '''
        IF OBJECT_ID('dbo.candidate_profiles', 'U') IS NOT NULL
        BEGIN
          IF COL_LENGTH('dbo.candidate_profiles', 'resume_file_name') IS NOT NULL AND COL_LENGTH('dbo.candidate_profiles', 'resume') IS NULL
          BEGIN
            ALTER TABLE dbo.candidate_profiles ADD resume VARBINARY(MAX) NULL;
            ALTER TABLE dbo.candidate_profiles DROP COLUMN resume_file_name;
          END
        END
        ''',
        '''
        -- Migration: update candidate_profiles FK to reference cid instead of id
        IF EXISTS (
          SELECT 1 FROM sys.foreign_keys 
          WHERE parent_object_id = OBJECT_ID('dbo.candidate_profiles') 
          AND referenced_object_id = OBJECT_ID('dbo.candidate_signup')
        )
        BEGIN
          DECLARE @fk_profiles NVARCHAR(200);
          SELECT @fk_profiles = name FROM sys.foreign_keys WHERE parent_object_id = OBJECT_ID('dbo.candidate_profiles') AND referenced_object_id = OBJECT_ID('dbo.candidate_signup');
          IF @fk_profiles IS NOT NULL 
          BEGIN 
            EXEC('ALTER TABLE dbo.candidate_profiles DROP CONSTRAINT ' + @fk_profiles); 
            ALTER TABLE dbo.candidate_profiles ADD CONSTRAINT FK_candidate_profiles_signup FOREIGN KEY (candidate_id) REFERENCES dbo.candidate_signup(cid);
          END
        END
        ''',
        '''
        -- Migration: convert candidate_profiles.candidate_id to NVARCHAR prefixed IDs
        IF OBJECT_ID('dbo.candidate_profiles', 'U') IS NOT NULL
           AND (SELECT system_type_id FROM sys.columns WHERE object_id = OBJECT_ID('dbo.candidate_profiles') AND name = 'candidate_id') IN (56, 127, 52)
        BEGIN
          DECLARE @fk_profiles2 NVARCHAR(200);
          SELECT @fk_profiles2 = name FROM sys.foreign_keys WHERE parent_object_id = OBJECT_ID('dbo.candidate_profiles') AND referenced_object_id = OBJECT_ID('dbo.candidate_signup');
          IF @fk_profiles2 IS NOT NULL 
          BEGIN 
            EXEC('ALTER TABLE dbo.candidate_profiles DROP CONSTRAINT ' + @fk_profiles2); 
          END

          DECLARE @uq_profiles NVARCHAR(200);
          SELECT @uq_profiles = name FROM sys.key_constraints 
          WHERE parent_object_id = OBJECT_ID('dbo.candidate_profiles') AND type = 'UQ';
          IF @uq_profiles IS NOT NULL
          BEGIN
            EXEC('ALTER TABLE dbo.candidate_profiles DROP CONSTRAINT ' + @uq_profiles);
          END

          ALTER TABLE dbo.candidate_profiles ALTER COLUMN candidate_id NVARCHAR(20) NOT NULL;
          UPDATE dbo.candidate_profiles
          SET candidate_id = 'CID' + FORMAT(TRY_CONVERT(INT, candidate_id), '000')
          WHERE TRY_CONVERT(INT, candidate_id) IS NOT NULL AND LEFT(candidate_id, 3) <> 'CID';

          ALTER TABLE dbo.candidate_profiles ADD CONSTRAINT UQ_candidate_profiles_candidate_id UNIQUE (candidate_id);
          ALTER TABLE dbo.candidate_profiles ADD CONSTRAINT FK_candidate_profiles_signup FOREIGN KEY (candidate_id) REFERENCES dbo.candidate_signup(cid);
        END
        ''',
        '''
        IF OBJECT_ID('dbo.applications', 'U') IS NULL
        BEGIN
          CREATE TABLE dbo.applications (
            id INT IDENTITY(1,1) PRIMARY KEY,
            candidate_id NVARCHAR(20) NOT NULL,
            job_id NVARCHAR(20) NOT NULL,
            status NVARCHAR(50) DEFAULT 'pending',
            applied_at DATETIME2 DEFAULT SYSUTCDATETIME(),
            CONSTRAINT UQ_application UNIQUE (candidate_id, job_id),
            CONSTRAINT FK_applications_candidate FOREIGN KEY (candidate_id) REFERENCES dbo.candidate_signup(cid),
            CONSTRAINT FK_applications_job FOREIGN KEY (job_id) REFERENCES dbo.jobs(jdid)
          );
        END
        ''',
        '''
        -- Migration: update applications FK to reference cid instead of id
        IF EXISTS (
          SELECT 1 FROM sys.foreign_keys 
          WHERE parent_object_id = OBJECT_ID('dbo.applications') 
          AND referenced_object_id = OBJECT_ID('dbo.candidate_signup')
        )
        BEGIN
          DECLARE @fk_applications NVARCHAR(200);
          SELECT @fk_applications = name FROM sys.foreign_keys WHERE parent_object_id = OBJECT_ID('dbo.applications') AND referenced_object_id = OBJECT_ID('dbo.candidate_signup');
          IF @fk_applications IS NOT NULL 
          BEGIN 
            EXEC('ALTER TABLE dbo.applications DROP CONSTRAINT ' + @fk_applications); 
            ALTER TABLE dbo.applications ADD CONSTRAINT FK_applications_candidate FOREIGN KEY (candidate_id) REFERENCES dbo.candidate_signup(cid);
          END
        END
        ''',
        '''
        -- Migration: convert applications.candidate_id to NVARCHAR prefixed IDs
        IF OBJECT_ID('dbo.applications', 'U') IS NOT NULL
           AND (SELECT system_type_id FROM sys.columns WHERE object_id = OBJECT_ID('dbo.applications') AND name = 'candidate_id') IN (56, 127, 52)
        BEGIN
          DECLARE @fk_applications2 NVARCHAR(200);
          SELECT @fk_applications2 = name FROM sys.foreign_keys WHERE parent_object_id = OBJECT_ID('dbo.applications') AND referenced_object_id = OBJECT_ID('dbo.candidate_signup');
          IF @fk_applications2 IS NOT NULL 
          BEGIN 
            EXEC('ALTER TABLE dbo.applications DROP CONSTRAINT ' + @fk_applications2); 
          END

          IF EXISTS (
            SELECT 1 FROM sys.key_constraints 
            WHERE parent_object_id = OBJECT_ID('dbo.applications') AND name = 'UQ_application'
          )
          BEGIN
            ALTER TABLE dbo.applications DROP CONSTRAINT UQ_application;
          END

          ALTER TABLE dbo.applications ALTER COLUMN candidate_id NVARCHAR(20) NOT NULL;
          UPDATE dbo.applications
          SET candidate_id = 'CID' + FORMAT(TRY_CONVERT(INT, candidate_id), '000')
          WHERE TRY_CONVERT(INT, candidate_id) IS NOT NULL AND LEFT(candidate_id, 3) <> 'CID';

          ALTER TABLE dbo.applications ADD CONSTRAINT UQ_application UNIQUE (candidate_id, job_id);
          ALTER TABLE dbo.applications ADD CONSTRAINT FK_applications_candidate FOREIGN KEY (candidate_id) REFERENCES dbo.candidate_signup(cid);
        END
        ''',
        '''
        -- Migration: update applications FK to reference jdid instead of id
        IF EXISTS (
          SELECT 1 FROM sys.foreign_keys 
          WHERE parent_object_id = OBJECT_ID('dbo.applications') 
          AND referenced_object_id = OBJECT_ID('dbo.jobs')
        )
        BEGIN
          DECLARE @fk_applications_job NVARCHAR(200);
          SELECT @fk_applications_job = name FROM sys.foreign_keys WHERE parent_object_id = OBJECT_ID('dbo.applications') AND referenced_object_id = OBJECT_ID('dbo.jobs');
          IF @fk_applications_job IS NOT NULL 
          BEGIN 
            EXEC('ALTER TABLE dbo.applications DROP CONSTRAINT ' + @fk_applications_job); 
            ALTER TABLE dbo.applications ADD CONSTRAINT FK_applications_job FOREIGN KEY (job_id) REFERENCES dbo.jobs(jdid);
          END
        END
        ''',
        '''
        -- Add matching_percentage column to applications table
        IF OBJECT_ID('dbo.applications', 'U') IS NOT NULL
        BEGIN
          IF COL_LENGTH('dbo.applications', 'matching_percentage') IS NULL
          BEGIN
            ALTER TABLE dbo.applications ADD matching_percentage FLOAT DEFAULT 0;
          END
        END
        ''',
        '''
        -- ATS WORKFLOW: Add match_score column to applications table
        IF OBJECT_ID('dbo.applications', 'U') IS NOT NULL
        BEGIN
          IF COL_LENGTH('dbo.applications', 'match_score') IS NULL
          BEGIN
            ALTER TABLE dbo.applications ADD match_score FLOAT NULL;
          END
        END
        ''',
        '''
        -- ATS WORKFLOW: Add shortlisted column to applications table
        IF OBJECT_ID('dbo.applications', 'U') IS NOT NULL
        BEGIN
          IF COL_LENGTH('dbo.applications', 'shortlisted') IS NULL
          BEGIN
            ALTER TABLE dbo.applications ADD shortlisted BIT NULL DEFAULT 0;
          END
        END
        ''',
        '''
        -- ATS WORKFLOW: Add ats_reasoning column to applications table
        IF OBJECT_ID('dbo.applications', 'U') IS NOT NULL
        BEGIN
          IF COL_LENGTH('dbo.applications', 'ats_reasoning') IS NULL
          BEGIN
            ALTER TABLE dbo.applications ADD ats_reasoning NVARCHAR(MAX) NULL;
          END
        END
        ''',
        '''
        -- ATS WORKFLOW: Add ats_analysis column to applications table (detailed structured matching data)
        IF OBJECT_ID('dbo.applications', 'U') IS NOT NULL
        BEGIN
          IF COL_LENGTH('dbo.applications', 'ats_analysis') IS NULL
          BEGIN
            ALTER TABLE dbo.applications ADD ats_analysis NVARCHAR(MAX) NULL;
          END
        END
        ''',
        '''
        -- ATS WORKFLOW: Add index for shortlisted queries
        IF NOT EXISTS (
          SELECT 1 FROM sys.indexes 
          WHERE name = 'IX_applications_shortlisted' 
          AND object_id = OBJECT_ID('dbo.applications')
        )
        BEGIN
          CREATE INDEX IX_applications_shortlisted ON dbo.applications(shortlisted, match_score DESC);
        END
        ''',
        '''
        -- ATS WORKFLOW: Add index for status-based queries
        IF NOT EXISTS (
          SELECT 1 FROM sys.indexes 
          WHERE name = 'IX_applications_status' 
          AND object_id = OBJECT_ID('dbo.applications')
        )
        BEGIN
          CREATE INDEX IX_applications_status ON dbo.applications(status, applied_at DESC);
        END
        ''',
        '''
        -- Drop saved_jobs table if it exists (feature removed)
        IF OBJECT_ID('dbo.saved_jobs', 'U') IS NOT NULL
        BEGIN
          -- Drop foreign keys first
          DECLARE @fk_drop_saved NVARCHAR(200);
          DECLARE fk_saved_cur CURSOR FOR
          SELECT name FROM sys.foreign_keys 
          WHERE parent_object_id = OBJECT_ID('dbo.saved_jobs');
          
          OPEN fk_saved_cur;
          FETCH NEXT FROM fk_saved_cur INTO @fk_drop_saved;
          WHILE @@FETCH_STATUS = 0
          BEGIN
            EXEC('ALTER TABLE dbo.saved_jobs DROP CONSTRAINT ' + @fk_drop_saved);
            FETCH NEXT FROM fk_saved_cur INTO @fk_drop_saved;
          END;
          CLOSE fk_saved_cur;
          DEALLOCATE fk_saved_cur;
          
          -- Drop the table
          DROP TABLE dbo.saved_jobs;
        END
        ''',
        '''
        IF OBJECT_ID('dbo.hr_login_sessions', 'U') IS NOT NULL
        BEGIN
          -- Drop foreign keys first
          DECLARE @fk_drop_hr_sessions NVARCHAR(200);
          DECLARE fk_hr_sessions_cur CURSOR FOR
          SELECT name FROM sys.foreign_keys 
          WHERE parent_object_id = OBJECT_ID('dbo.hr_login_sessions');
          
          OPEN fk_hr_sessions_cur;
          FETCH NEXT FROM fk_hr_sessions_cur INTO @fk_drop_hr_sessions;
          WHILE @@FETCH_STATUS = 0
          BEGIN
            EXEC('ALTER TABLE dbo.hr_login_sessions DROP CONSTRAINT ' + @fk_drop_hr_sessions);
            FETCH NEXT FROM fk_hr_sessions_cur INTO @fk_drop_hr_sessions;
          END;
          CLOSE fk_hr_sessions_cur;
          DEALLOCATE fk_hr_sessions_cur;
          
          -- Drop the table
          DROP TABLE dbo.hr_login_sessions;
        END
        ''',
        '''
        IF OBJECT_ID('dbo.candidate_login_sessions', 'U') IS NOT NULL
        BEGIN
          DROP TABLE dbo.candidate_login_sessions;
        END
        ''',
        '''
        IF OBJECT_ID('dbo.login_history', 'U') IS NULL
        BEGIN
          CREATE TABLE dbo.login_history (
            id INT IDENTITY(1,1) PRIMARY KEY,
            email NVARCHAR(255) NOT NULL,
            user_type NVARCHAR(20) NOT NULL CHECK (user_type IN ('HR', 'candidate')),
            ip_address NVARCHAR(100),
            user_agent NVARCHAR(500),
            status NVARCHAR(20) NOT NULL CHECK (status IN ('success', 'failed')),
            failure_reason NVARCHAR(255),
            attempted_at DATETIME2 DEFAULT SYSUTCDATETIME()
          );
        END
        ''',
        '''
        IF NOT EXISTS (
          SELECT name FROM sys.indexes WHERE name = 'idx_login_history_email' AND object_id = OBJECT_ID('dbo.login_history')
        )
        BEGIN
          CREATE INDEX idx_login_history_email ON dbo.login_history(email, user_type);
        END
        ''',
        '''
        IF OBJECT_ID('dbo.CandidateAuth', 'U') IS NULL
        BEGIN
          CREATE TABLE dbo.CandidateAuth (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name NVARCHAR(255) NOT NULL,
            email NVARCHAR(255) NULL,
            phone NVARCHAR(20) NULL,
            password_hash NVARCHAR(255) NOT NULL,
            otp NVARCHAR(6) NULL,
            otp_expiry DATETIME2 NULL,
            is_verified BIT NOT NULL CONSTRAINT DF_CandidateAuth_is_verified DEFAULT 0,
            created_at DATETIME2 NOT NULL CONSTRAINT DF_CandidateAuth_created DEFAULT SYSUTCDATETIME(),
            updated_at DATETIME2 NOT NULL CONSTRAINT DF_CandidateAuth_updated DEFAULT SYSUTCDATETIME()
          );
        END
        ''',
        '''
        IF OBJECT_ID('dbo.CandidateAuth', 'U') IS NOT NULL
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM sys.indexes WHERE name = 'IX_CandidateAuth_Email' AND object_id = OBJECT_ID('dbo.CandidateAuth')
          )
          BEGIN
            CREATE UNIQUE INDEX IX_CandidateAuth_Email ON dbo.CandidateAuth(email) WHERE email IS NOT NULL;
          END
          IF NOT EXISTS (
            SELECT 1 FROM sys.indexes WHERE name = 'IX_CandidateAuth_Phone' AND object_id = OBJECT_ID('dbo.CandidateAuth')
          )
          BEGIN
            CREATE UNIQUE INDEX IX_CandidateAuth_Phone ON dbo.CandidateAuth(phone) WHERE phone IS NOT NULL;
          END
        END
        ''',
        '''
        IF OBJECT_ID('dbo.HRAuth', 'U') IS NULL
        BEGIN
          CREATE TABLE dbo.HRAuth (
            id INT IDENTITY(1,1) PRIMARY KEY,
            full_name NVARCHAR(255) NOT NULL,
            email NVARCHAR(255) UNIQUE NOT NULL,
            company NVARCHAR(255) NOT NULL,
            password_hash NVARCHAR(255) NOT NULL,
            otp NVARCHAR(6) NULL,
            otp_expiry DATETIME2 NULL,
            is_verified BIT NOT NULL CONSTRAINT DF_HRAuth_is_verified DEFAULT 0,
            created_at DATETIME2 NOT NULL CONSTRAINT DF_HRAuth_created DEFAULT SYSUTCDATETIME(),
            updated_at DATETIME2 NOT NULL CONSTRAINT DF_HRAuth_updated DEFAULT SYSUTCDATETIME()
          );
        END
        ''',
        '''
        IF OBJECT_ID('dbo.HRAuth', 'U') IS NOT NULL
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM sys.indexes WHERE name = 'IX_HRAuth_Email' AND object_id = OBJECT_ID('dbo.HRAuth')
          )
          BEGIN
            CREATE UNIQUE INDEX IX_HRAuth_Email ON dbo.HRAuth(email);
          END
        END
        '''
    ]

    with get_conn() as conn:
        cursor = conn.cursor()
        for stmt in statements:
            cursor.execute(stmt)
    
    # Run additional migrations from files
    run_migrations()
