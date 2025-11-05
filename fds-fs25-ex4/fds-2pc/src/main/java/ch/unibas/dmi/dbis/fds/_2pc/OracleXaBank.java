package ch.unibas.dmi.dbis.fds._2pc;


import java.sql.SQLException;


/**
 * Check the XA stuff here --> https://docs.oracle.com/cd/B14117_01/java.101/b10979/xadistra.htm
 *
 * @author Alexander Stiemer (alexander.stiemer at unibas.ch)
 */
public class OracleXaBank extends AbstractOracleXaBank {


    public OracleXaBank( final String BIC, final String jdbcConnectionString, final String dbmsUsername, final String dbmsPassword ) throws SQLException {
        super( BIC, jdbcConnectionString, dbmsUsername, dbmsPassword );
    }


    @Override
     public float getBalance(final String iban) throws SQLException {
         try (var c = this.getXaConnection().getConnection();
              var ps = c.prepareStatement("SELECT balance FROM account WHERE iban = ?")) {
             ps.setString(1, iban);
             try (var rs = ps.executeQuery()) {
                 if (!rs.next()) return Float.NaN;
                 return rs.getFloat(1);
             }
         }
     }

     /**
      * Distributed transfer using XA 2PC:
      *  - THIS bank debits (source).
      *  - TO_BANK credits (destination).
      * If any step fails, both branches are rolled back to preserve atomicity.
      *
      * Assumptions:
      *  - Table: account(iban PRIMARY KEY, balance NUMERIC)
      *  - Capacity guard for destination (<= 15000) enforced explicitly here.
      */
     @Override
     public void transfer(final AbstractOracleXaBank TO_BANK,
                          final String ibanFrom, final String ibanTo, final float value) {
         Xid xidFrom = null, xidTo = null;

         try {
             // 1) Start FROM branch with a NEW global XID
             xidFrom = this.startTransaction();

             // 2) Start TO branch with SAME global id (different branch qualifier on TO bank)
             xidTo = TO_BANK.startTransaction(xidFrom);

             // 3) Business operations under XA control (no local commit!)

             // FROM side: debit with sufficient-funds guard
             try (var cFrom = this.getXaConnection().getConnection()) {
                 cFrom.setAutoCommit(false);
                 try (var ps = cFrom.prepareStatement(
                         "UPDATE account SET balance = balance - ? " +
                         "WHERE iban = ? AND balance >= ?")) {
                     ps.setFloat(1, value);
                     ps.setString(2, ibanFrom);
                     ps.setFloat(3, value);
                     final int updated = ps.executeUpdate();
                     if (updated != 1) {
                         throw new SQLException("Debit failed: missing account or insufficient funds.");
                     }
                 }
             }

             // TO side: credit with capacity guard (<= 15000)
             try (var cTo = TO_BANK.getXaConnection().getConnection()) {
                 cTo.setAutoCommit(false);

                 float current;
                 try (var ps = cTo.prepareStatement(
                         "SELECT balance FROM account WHERE iban = ? FOR UPDATE")) {
                     ps.setString(1, ibanTo);
                     try (var rs = ps.executeQuery()) {
                         if (!rs.next()) {
                             throw new SQLException("Credit failed: destination account not found.");
                         }
                         current = rs.getFloat(1);
                     }
                 }

                 if (current + value > 15000.0f) {
                     throw new SQLException("Credit failed: would exceed account capacity.");
                 }

                 try (var ps = cTo.prepareStatement(
                         "UPDATE account SET balance = balance + ? WHERE iban = ?")) {
                     ps.setFloat(1, value);
                     ps.setString(2, ibanTo);
                     final int updated = ps.executeUpdate();
                     if (updated != 1) {
                         throw new SQLException("Credit failed: update did not affect exactly one row.");
                     }
                 }
             }

             // 4) End both branches successfully (ready to prepare)
             this.endTransaction(xidFrom, false);
             TO_BANK.endTransaction(xidTo, false);

             // 5) PREPARE both branches
             final XAResource xaFrom = this.getXaResource();
             final XAResource xaTo   = TO_BANK.getXaResource();
             final int pFrom = xaFrom.prepare(xidFrom);
             final int pTo   = xaTo.prepare(xidTo);

             // 6) DECIDE: commit if both prepared OK, else rollback both
             if (pFrom == XAResource.XA_OK && pTo == XAResource.XA_OK) {
                 xaFrom.commit(xidFrom, false);   // two-phase commit (onePhase=false)
                 xaTo.commit(xidTo, false);
             } else {
                 xaFrom.rollback(xidFrom);
                 xaTo.rollback(xidTo);
                 throw new RuntimeException("Prepare phase failed — rolled back both branches.");
             }

         } catch (Exception e) {
             // Best-effort cleanup on ANY error:
             try { if (xidFrom != null) this.endTransaction(xidFrom, true); } catch (Exception ignore) {}
             try { if (xidTo   != null) TO_BANK.endTransaction(xidTo, true); } catch (Exception ignore) {}
             try { if (xidFrom != null) this.getXaResource().rollback(xidFrom); } catch (Exception ignore) {}
             try { if (xidTo   != null) TO_BANK.getXaResource().rollback(xidTo); } catch (Exception ignore) {}

             throw new RuntimeException("Distributed transfer failed and was rolled back.", e);
         }
    }
}
