CREATE TABLE BranchServices (
    ServiceID INT,
    BranchNo INT,
    ServiceName VARCHAR(255) NOT NULL,
    Description TEXT,
	primary key(ServiceID),
    foreign key(BranchNo) 
        REFERENCES Branches(BranchNo) 
        ON DELETE CASCADE
);
ALTER TABLE Staff
ADD Department varchar(30),
    CONSTRAINT chk_department CHECK (Department IN ('Sales', 'PR', 'IT'));
INSERT INTO BranchServices (ServiceID, BranchNo, ServiceName, Description)
VALUES
(1, 'B001', 'Property Appraisal', 'Professional appraisal of property value.'),
(2, 'B002', 'Mortgage Assistance', 'Guidance on mortgage processes.'),
(3, 'B001', 'Customer Support', 'Helpdesk for property inquiries.'),
(4, 'B003', 'Property Inspection', 'On-site property inspections.'),
(5, 'B002', 'Legal Assistance', 'Support with legal documentation.'),
(6, 'B004', 'Marketing Services', 'Property advertisement and promotions.');
DELETE FROM BranchServices
WHERE ServiceName = 'Mortgage Assistance';


	