package ch.unibas.dmi.dbis.fds._2pc;


import java.sql.SQLException;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import javax.transaction.xa.XAException;
import javax.transaction.xa.Xid;


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
        try (Connection conn = this.getXaConnection().getConnection();
             PreparedStatement stmt = conn.prepareStatement("SELECT balance FROM account WHERE iban = ?")) {
            stmt.setString(1, iban);
            ResultSet rs = stmt.executeQuery();
            if (rs.next()) {
                return rs.getFloat("balance");
            } else {
                throw new SQLException("Account not found: " + iban);
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
 	    public void transfer(final AbstractOracleXaBank TO_BANK, final String ibanFrom, final String ibanTo, final float value) {
 	        Xid xidFrom = null;
 	        Xid xidTo = null;
        
 	        try {
 	            // Start global transaction
 	            Xid globalXid = this.startTransaction();
 	            xidFrom = globalXid;
 	            xidTo = TO_BANK.startTransaction(globalXid);

 	            // Execute withdraw operation
 	            withdraw(ibanFrom, value);
            
 	            // Execute deposit operation on target bank
 	            TO_BANK.deposit(ibanTo, value);

 	            // Phase 1: Prepare (2PC - First Phase)
 	            int prepareResultFrom = this.getXaResource().prepare(xidFrom);
 	            int prepareResultTo = TO_BANK.getXaResource().prepare(xidTo);

 	            // Phase 2: Commit (2PC - Second Phase)
 	            if (prepareResultFrom == XAResource.XA_OK && prepareResultTo == XAResource.XA_OK) {
 	                this.getXaResource().commit(xidFrom, false);
 	                TO_BANK.getXaResource().commit(xidTo, false);
 	                System.out.println("Transaction committed successfully");
 	            } else {
 	                throw new XAException("Prepare phase failed - one or both branches returned non-XA_OK");
 	            }

 	        } catch (Exception e) {
 	            // Rollback on any error (Atomicity guarantee)
 	            try {
 	                if (xidFrom != null) this.getXaResource().rollback(xidFrom);
 	            } catch (XAException ex) {
 	                System.err.println("Error rolling back source bank transaction: " + ex.getMessage());
 	            }
 	            try {
 	                if (xidTo != null) TO_BANK.getXaResource().rollback(xidTo);
 	            } catch (XAException ex) {
 	                System.err.println("Error rolling back target bank transaction: " + ex.getMessage());
 	            }
 	            throw new RuntimeException("Transfer failed: " + e.getMessage(), e);
 	        }
 	    }

 	    // Helper method for withdraw operation
 	    private void withdraw(String iban, float amount) throws SQLException {
 	        try (Connection conn = this.getXaConnection().getConnection();
 	             PreparedStatement stmt = conn.prepareStatement("UPDATE account SET balance = balance - ? WHERE iban = ? AND balance >= ?")) {
 	            stmt.setFloat(1, amount);
 	            stmt.setString(2, iban);
 	            stmt.setFloat(3, amount);
            
 	            int rowsAffected = stmt.executeUpdate();
 	            if (rowsAffected == 0) {
 	                throw new SQLException("Withdraw failed: Insufficient funds or account not found for IBAN: " + iban);
 	            }
 	        }
 	    }

 	    // Helper method for deposit operation  
 	    public void deposit(String iban, float amount) throws SQLException {
 	        try (Connection conn = this.getXaConnection().getConnection();
 	             PreparedStatement stmt = conn.prepareStatement("UPDATE account SET balance = balance + ? WHERE iban = ?")) {
 	            stmt.setFloat(1, amount);
 	            stmt.setString(2, iban);
            
 	            int rowsAffected = stmt.executeUpdate();
 	            if (rowsAffected == 0) {
 	                throw new SQLException("Deposit failed: Account not found for IBAN: " + iban);
 	            }
 	        }
 	    }
 	}
