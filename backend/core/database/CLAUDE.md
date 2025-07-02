# Database & ORM - CLAUDE.md

## 🎯 Context & Purpose

This is the **Database & ORM** worktree focused on SQL database operations, multi-tenant data management, and repository patterns for Copilot Canvas. This handles all SQLAlchemy models, database connections, and structured data operations.

**Primary Focus Areas:**
- SQLAlchemy ORM models and relationships
- Multi-tenant database isolation and management
- Repository pattern implementation
- Database migrations and schema management
- PostgreSQL and SQLite database support

## 🏗️ Database Architecture

### System Overview
```
Application → Repository Layer → ORM Models → Database Adapters → SQL Databases
     ↓              ↓              ↓              ↓               ↓
  Business       Data Access    Schema Def.   Connection     PostgreSQL
   Logic         Patterns        & Relations   Management      /SQLite
```

### Core Components

1. **ORM Models** (`database/models/`)
   - **models.py**: 15+ SQLAlchemy models for all entities
   - **base.py**: Base model with common fields
   - Relationship definitions and constraints
   - Multi-tenant field patterns

2. **Database Management** (`database/`)
   - **manager.py**: Database connection management
   - **factory.py**: Multi-tenant database factory
   - **database.py**: Legacy SQLite interface
   - **tenant_config.py**: Tenant configuration management

3. **Repository Pattern** (`repositories/`)
   - **base_repository.py**: Generic repository base
   - **ticket_repository.py**: Ticket-specific operations
   - **integrated_object_repository.py**: Cross-platform objects
   - Query abstraction and optimization

4. **Migration & Config**
   - **migration_layer.py**: ORM/Legacy transition support
   - **tenant_config.py**: Multi-tenant settings
   - Schema versioning and upgrades

### Key Design Patterns

- **Repository Pattern**: Data access abstraction
- **Factory Pattern**: Database instance creation
- **Active Record**: SQLAlchemy ORM pattern
- **Multi-tenancy**: Tenant-isolated data
- **Migration**: Schema evolution support

## 🚀 Development Commands

### Environment Setup
```bash
# Virtual environment (from backend directory)
source venv/bin/activate

# Install database dependencies
pip install sqlalchemy alembic psycopg2-binary

# Verify ORM models
python -c "from core.database.models import Base, Ticket; print('✅ ORM Models OK')"
```

### Database Operations
```bash
# Test database connection
python -c "
from core.database.manager import get_db_manager
manager = get_db_manager('wedosoft', 'freshdesk')
print('✅ Database manager ready')
"

# Test repository pattern
python -c "
from core.repositories.ticket_repository import TicketRepository
repo = TicketRepository()
print('✅ Repository pattern OK')
"

# Test multi-tenant factory
python -c "
from core.database.factory import get_database
db = get_database('test_tenant', 'freshdesk')
print('✅ Multi-tenant factory OK')
"
```

### ORM Testing
```bash
# Test model relationships
python -c "
from core.database.models import Ticket, Agent, Company
print('✅ Model relationships defined')
"

# Test database factory
python -c "
from core.database.factory import DatabaseFactory
factory = DatabaseFactory()
print('✅ Database factory ready')
"
```

## 🔧 Key Environment Variables

```bash
# Database Configuration
USE_ORM=true                    # Enable ORM mode
DATABASE_TYPE=sqlite            # sqlite/postgresql

# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=freshdesk_app
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# SQLite Configuration (development)
SQLITE_DATA_DIR=./core/data

# Multi-tenant Configuration
TENANT_ID_VALIDATION=strict
MAX_TENANTS=1000
ALLOW_TENANT_CREATION=true
TENANT_ISOLATION=company

# Performance
CONNECTION_POOL_SIZE=20
QUERY_TIMEOUT=30
```

## 📁 Directory Structure

```
core/database/
├── __init__.py              # Module exports
├── models/                  # SQLAlchemy models
│   ├── __init__.py
│   ├── models.py           # Main ORM models
│   └── base.py             # Base model class
├── manager.py              # Database connection management
├── factory.py              # Multi-tenant database factory
├── database.py             # Legacy SQLite interface
├── tenant_config.py        # Tenant configuration
└── postgresql_database.py  # PostgreSQL implementation

core/repositories/
├── __init__.py
├── base_repository.py      # Generic repository base
├── ticket_repository.py    # Ticket operations
└── integrated_object_repository.py  # Cross-platform objects

core/
├── migration_layer.py      # ORM/Legacy migration support
└── dependencies.py         # Database dependency injection
```

## 🔍 Common Tasks

### ORM Model Usage
```python
# Working with SQLAlchemy models
from core.database.models import Ticket, Agent, Company, Conversation
from core.database.manager import get_db_session

# Create database session
session = get_db_session(tenant_id="wedosoft", platform="freshdesk")

# Create new entities
company = Company(
    name="Wedosoft",
    platform="freshdesk",
    subscription_plan="enterprise"
)

agent = Agent(
    agent_id="agent_123",
    name="John Doe",
    email="john@wedosoft.com",
    company=company
)

ticket = Ticket(
    ticket_id="ticket_456",
    subject="Login Issues",
    description="User cannot access account",
    status="open",
    priority="high",
    company=company,
    requester_email="user@example.com"
)

# Save to database
session.add_all([company, agent, ticket])
session.commit()
```

### Repository Pattern Usage
```python
# Using repository pattern for data access
from core.repositories.ticket_repository import TicketRepository
from core.repositories.integrated_object_repository import IntegratedObjectRepository

# Initialize repositories
ticket_repo = TicketRepository(tenant_id="wedosoft", platform="freshdesk")
object_repo = IntegratedObjectRepository()

# Query tickets
recent_tickets = await ticket_repo.get_recent_tickets(limit=10)
high_priority_tickets = await ticket_repo.get_by_priority("high")
tickets_by_agent = await ticket_repo.get_by_agent("agent_123")

# Search tickets
search_results = await ticket_repo.search_tickets(
    query="login issues",
    filters={"status": "open", "priority": ["high", "urgent"]}
)

# Create new ticket
new_ticket = await ticket_repo.create_ticket({
    "subject": "Password Reset Request",
    "description": "User needs password reset",
    "requester_email": "user@example.com",
    "priority": "medium"
})
```

### Multi-tenant Database Management
```python
# Multi-tenant database operations
from core.database.factory import DatabaseFactory, get_database
from core.database.manager import get_db_manager

# Get tenant-specific database
db = get_database(tenant_id="wedosoft", platform="freshdesk")
await db.connect()

# Create tables for tenant
await db.create_tables()

# Get database manager for tenant
manager = get_db_manager(tenant_id="wedosoft", platform="freshdesk")

# Switch between tenants
tenant1_db = get_database("tenant1", "freshdesk")
tenant2_db = get_database("tenant2", "freshdesk")

# Each tenant has isolated data
tenant1_tickets = await tenant1_db.get_tickets()
tenant2_tickets = await tenant2_db.get_tickets()  # Completely separate
```

### Database Factory Usage
```python
# Database factory for dynamic tenant management
from core.database.factory import DatabaseFactory, DatabaseType

factory = DatabaseFactory()

# Auto-detect database type from environment
auto_db = factory.create_database("auto_tenant", "freshdesk")

# Force specific database type
sqlite_db = factory.create_database(
    tenant_id="dev_tenant",
    platform="freshdesk",
    db_type=DatabaseType.SQLITE
)

postgresql_db = factory.create_database(
    tenant_id="prod_tenant",
    platform="freshdesk",
    db_type=DatabaseType.POSTGRESQL
)

# Connection management
await sqlite_db.connect()
await postgresql_db.connect()
```

## 🎯 Multi-tenant Patterns

### Tenant Isolation
```python
# Ensure complete tenant data isolation
from core.database.models import Ticket
from core.database.manager import get_db_session

async def get_tenant_tickets(tenant_id: str, platform: str):
    """
    Always filter by tenant_id to ensure data isolation
    """
    session = get_db_session(tenant_id, platform)
    
    # CRITICAL: Always filter by tenant
    tickets = session.query(Ticket).filter(
        Ticket.company.has(name=tenant_id),
        Ticket.platform == platform
    ).all()
    
    return tickets

# NEVER query without tenant filtering
# BAD: session.query(Ticket).all()  # This exposes all tenants' data
# GOOD: session.query(Ticket).filter(Ticket.company.has(name=tenant_id))
```

### Dynamic Schema Management
```python
# Handle tenant-specific schemas (PostgreSQL)
from core.database.postgresql_database import PostgreSQLDatabase

class TenantSchemaManager:
    def __init__(self, tenant_id: str, platform: str):
        self.tenant_id = tenant_id
        self.platform = platform
        self.schema_name = f"tenant_{tenant_id}"
    
    async def create_tenant_schema(self):
        """Create dedicated schema for tenant"""
        db = PostgreSQLDatabase(self.tenant_id, self.platform)
        await db.execute_raw(f"CREATE SCHEMA IF NOT EXISTS {self.schema_name}")
        await db.create_tables_in_schema(self.schema_name)
    
    async def migrate_tenant_data(self, from_version: str, to_version: str):
        """Perform tenant-specific migrations"""
        migration_script = self.get_migration_script(from_version, to_version)
        db = PostgreSQLDatabase(self.tenant_id, self.platform)
        await db.execute_raw(migration_script)
```

### Repository Inheritance
```python
# Extend base repository for specific entities
from core.repositories.base_repository import BaseRepository
from core.database.models import Conversation

class ConversationRepository(BaseRepository[Conversation]):
    def __init__(self, tenant_id: str, platform: str):
        super().__init__(Conversation, tenant_id, platform)
    
    async def get_by_ticket(self, ticket_id: str) -> List[Conversation]:
        """Get all conversations for a ticket"""
        return await self.query().filter(
            Conversation.ticket_id == ticket_id
        ).all()
    
    async def get_latest_conversation(self, ticket_id: str) -> Optional[Conversation]:
        """Get most recent conversation for ticket"""
        return await self.query().filter(
            Conversation.ticket_id == ticket_id
        ).order_by(Conversation.created_at.desc()).first()
    
    async def search_conversations(self, query: str, limit: int = 50) -> List[Conversation]:
        """Search conversations by content"""
        return await self.query().filter(
            Conversation.content.ilike(f"%{query}%")
        ).limit(limit).all()
```

## 🚨 Important Notes

### Security & Data Isolation
- **NEVER** query without tenant_id filtering
- Always validate tenant access in repository methods
- Use parameterized queries to prevent SQL injection
- Implement row-level security for PostgreSQL

### Performance Considerations
- Use connection pooling for better performance
- Implement query optimization in repositories
- Add database indexes for frequently queried fields
- Use async operations for I/O bound database operations

### Migration Management
- Test migrations on development data first
- Backup databases before production migrations
- Use transaction rollback for failed migrations
- Document schema changes and migration procedures

## 🔗 Integration Points

### Vector Database Integration
```python
# ORM entities can be linked to vector storage
from core.database.models import IntegratedObject
from core.database.vectordb import vector_db

async def sync_orm_to_vector(ticket: Ticket):
    """Sync ORM ticket to vector database"""
    
    # Create integrated object
    integrated_obj = IntegratedObject(
        id=f"{ticket.company.name}_{ticket.platform}_{ticket.ticket_id}",
        original_id=ticket.ticket_id,
        platform=ticket.platform,
        object_type="ticket",
        title=ticket.subject,
        content=ticket.description,
        tenant_id=ticket.company.name
    )
    
    # Save to SQL
    session.add(integrated_obj)
    session.commit()
    
    # Also store in vector DB
    await vector_db.insert_vectors("documents", [{
        "id": integrated_obj.id,
        "vector": await generate_embedding(ticket.description),
        "metadata": {
            "tenant_id": ticket.company.name,
            "platform": ticket.platform,
            "doc_type": "ticket",
            "content": ticket.description
        }
    }])
```

### API Layer Integration
```python
# Repositories used in API endpoints
from fastapi import APIRouter, Depends
from core.repositories.ticket_repository import TicketRepository
from core.dependencies import get_tenant_context

@router.get("/api/tickets")
async def get_tickets(
    tenant_context = Depends(get_tenant_context),
    limit: int = 20
):
    repo = TicketRepository(
        tenant_id=tenant_context.tenant_id,
        platform=tenant_context.platform
    )
    
    tickets = await repo.get_recent_tickets(limit=limit)
    
    return {
        "tickets": [ticket.to_dict() for ticket in tickets],
        "total": len(tickets)
    }

@router.post("/api/tickets")
async def create_ticket(
    ticket_data: dict,
    tenant_context = Depends(get_tenant_context)
):
    repo = TicketRepository(
        tenant_id=tenant_context.tenant_id,
        platform=tenant_context.platform
    )
    
    ticket = await repo.create_ticket(ticket_data)
    return {"ticket": ticket.to_dict()}
```

### Migration Layer Integration
```python
# Bridge between ORM and legacy systems
from core.migration_layer import store_integrated_object_with_migration

async def store_with_migration_support(data: dict, use_orm: bool = True):
    """
    Store data with support for both ORM and legacy systems
    """
    if use_orm:
        # Use repository pattern
        repo = IntegratedObjectRepository()
        await repo.create(data)
    else:
        # Use legacy storage
        await store_integrated_object_with_migration(data, use_legacy=True)
```

## 📚 Key Files to Know

- `core/database/models/models.py` - Main SQLAlchemy ORM models
- `core/database/manager.py` - Database connection management
- `core/database/factory.py` - Multi-tenant database factory
- `core/repositories/base_repository.py` - Repository pattern base
- `core/migration_layer.py` - ORM/Legacy migration support

## 🔄 Development Workflow

1. **Start Development**: Verify database connectivity
2. **Model Changes**: Update SQLAlchemy models if needed
3. **Repository Methods**: Add new data access methods
4. **Test Queries**: Verify repository operations
5. **Migration**: Create migration scripts for schema changes
6. **Performance**: Monitor query performance and optimize

## 🚀 Advanced Features

### Custom Query Builder
```python
# Build complex queries dynamically
class QueryBuilder:
    def __init__(self, model_class, session):
        self.model_class = model_class
        self.session = session
        self.query = session.query(model_class)
        self.filters = []
    
    def filter_by_tenant(self, tenant_id: str, platform: str):
        if hasattr(self.model_class, 'company'):
            self.query = self.query.filter(
                self.model_class.company.has(name=tenant_id)
            )
        if hasattr(self.model_class, 'platform'):
            self.query = self.query.filter(
                self.model_class.platform == platform
            )
        return self
    
    def filter_by_date_range(self, start_date, end_date, date_field='created_at'):
        field = getattr(self.model_class, date_field)
        self.query = self.query.filter(field.between(start_date, end_date))
        return self
    
    def filter_by_status(self, status_list: List[str]):
        self.query = self.query.filter(
            self.model_class.status.in_(status_list)
        )
        return self
    
    def order_by(self, field: str, desc: bool = False):
        order_field = getattr(self.model_class, field)
        if desc:
            order_field = order_field.desc()
        self.query = self.query.order_by(order_field)
        return self
    
    def paginate(self, page: int, per_page: int):
        offset = (page - 1) * per_page
        self.query = self.query.offset(offset).limit(per_page)
        return self
    
    def execute(self):
        return self.query.all()

# Usage
builder = QueryBuilder(Ticket, session)
tickets = (builder
    .filter_by_tenant("wedosoft", "freshdesk")
    .filter_by_status(["open", "pending"])
    .filter_by_date_range(start_date, end_date)
    .order_by("created_at", desc=True)
    .paginate(page=1, per_page=20)
    .execute()
)
```

### Database Health Monitoring
```python
# Monitor database health and performance
class DatabaseHealthMonitor:
    def __init__(self):
        self.metrics = {}
    
    async def check_connection_health(self, tenant_id: str, platform: str):
        """Check if database connection is healthy"""
        try:
            db = get_database(tenant_id, platform)
            await db.execute_raw("SELECT 1")
            return {"status": "healthy", "response_time": 0.1}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def check_query_performance(self, tenant_id: str, platform: str):
        """Monitor query performance"""
        start_time = time.time()
        
        repo = TicketRepository(tenant_id, platform)
        tickets = await repo.get_recent_tickets(limit=10)
        
        end_time = time.time()
        query_time = end_time - start_time
        
        return {
            "query_time": query_time,
            "records_returned": len(tickets),
            "performance_rating": "good" if query_time < 1.0 else "slow"
        }
    
    async def get_database_stats(self, tenant_id: str, platform: str):
        """Get database statistics"""
        session = get_db_session(tenant_id, platform)
        
        stats = {
            "total_tickets": session.query(Ticket).count(),
            "total_agents": session.query(Agent).count(),
            "total_companies": session.query(Company).count(),
            "database_size": await self.get_database_size(tenant_id, platform)
        }
        
        return stats
```

### Automated Backup System
```python
# Implement automated backup for tenant data
class TenantBackupManager:
    def __init__(self):
        self.backup_schedule = {}
    
    async def backup_tenant_data(self, tenant_id: str, platform: str):
        """Create backup of tenant data"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{tenant_id}_{platform}_{timestamp}.sql"
        
        db = get_database(tenant_id, platform)
        
        if isinstance(db, PostgreSQLDatabase):
            await self.backup_postgresql(tenant_id, platform, backup_filename)
        else:
            await self.backup_sqlite(tenant_id, platform, backup_filename)
        
        return backup_filename
    
    async def schedule_automatic_backups(self, tenant_id: str, interval_hours: int = 24):
        """Schedule automatic backups"""
        async def backup_task():
            while True:
                try:
                    await self.backup_tenant_data(tenant_id, "freshdesk")
                    logger.info(f"Backup completed for tenant {tenant_id}")
                except Exception as e:
                    logger.error(f"Backup failed for tenant {tenant_id}: {e}")
                
                await asyncio.sleep(interval_hours * 3600)
        
        task = asyncio.create_task(backup_task())
        self.backup_schedule[tenant_id] = task
```

---

*This worktree focuses exclusively on database operations and ORM patterns. For vector storage, use the vector-db worktree. For data ingestion, use the data-pipeline worktree.*
