package Larkspur {
    doc /* A parcel-locker network, invented for the kit's example. */

    package CapabilityTaxonomy {
        doc /* The two things the network can do. */

        abstract occurrence def Capability;
        occurrence def ParcelIntake :> Capability;
        occurrence def ParcelRouting :> Capability;
    }

    package ResourceKit {
        doc /* What a site is built from. */

        abstract part def SiteMember;
        part def Locker :> SiteMember;
        part def Scanner :> SiteMember;

        part def Site {
            part locker : Locker[1];
            part scanner : Scanner[0..1];
        }
    }
}
