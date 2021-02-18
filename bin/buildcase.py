#!/usr/bin/env python
import os, sys
cesmroot = os.environ.get('CESM_ROOT')
s2sfcstroot = os.path.join(os.path.dirname(os.path.join(os.path.abspath(__file__))), os.path.pardir)

if cesmroot is None:
    raise SystemExit("ERROR: CESM_ROOT must be defined in environment")

_LIBDIR = os.path.join(cesmroot,"cime","scripts","Tools")
sys.path.append(_LIBDIR)
_LIBDIR = os.path.join(cesmroot,"cime","scripts","lib")
sys.path.append(_LIBDIR)

import datetime, glob, shutil
import CIME.build as build
from standard_script_setup import *
from CIME.case             import Case
from CIME.utils            import safe_copy
from argparse              import RawTextHelpFormatter
from CIME.locked_files          import lock_file, unlock_file

def parse_command_line(args, description):
    parser = argparse.ArgumentParser(description=description,
                                     formatter_class=RawTextHelpFormatter)
    CIME.utils.setup_standard_logging_options(parser)
    parser.add_argument("--date",
                        help="Specify a start Date")
    #parser.add_argument("--model",help="Specify a caseroot (cesm2cam6, b.e21.SMYLE.f09_g17.)", default="b.e21.SMYLE.f09_g17")
    parser.add_argument("--model",help="Specify a case (cesm2cam6, cesm2smyle)", default="cesm2smyle")

    args = CIME.utils.parse_args_and_handle_standard_logging_options(args, parser)
    cdate = os.getenv("CYLC_TASK_CYCLE_POINT")

    if args.date:
        try:
            date = datetime.datetime.strptime(args.date, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Incorrect data format, should be YYYY-MM-DD or YYYY-MM")
    elif cdate:
        date = datetime.datetime.strptime(cdate, '%Y-%m-%d')
    else:
        date = datetime.date.today()
        date = date.replace(day=date.day-1)

    return date.strftime("%Y-%m-%d"), args.model
    #return date.strftime("%Y-%m-%d"), args.basecasename

def stage_refcase(rundir, refdir, date, basecasename):
    if not os.path.isdir(rundir):
        os.makedirs(rundir)
    #if basecasename == "b.e21.SMYLE.f09_g17":
    #if model == "cesm2smyle":
    nfname = "b.e21.SMYLE_IC.f09_g17"
    #else:
    #   nfname = "b.e21.f09_g17"
    print ("refdir="+refdir)
    print ("rundir="+rundir)
    for reffile in glob.iglob(refdir+"/*"):
        print ("theNEWFILE="+reffile)
        if os.path.basename(reffile).startswith("rpointer"):
            safe_copy(reffile, rundir)
        else:
            newfile = os.path.basename(reffile)
            #newfile = "{}.cice.r.{}-00000.nc".format(nfname,date)
            newfile = os.path.join(rundir,newfile)            
            if not "cam.i" in newfile:
                if os.path.lexists(newfile):
                    os.unlink(newfile)
                os.symlink(reffile, newfile)

def per_run_case_updates(case, date, sdrestdir, user_mods_dir, rundir):
    caseroot = case.get_value("CASEROOT")
    basecasename = os.path.basename(caseroot)[:-6]
    member = os.path.basename(caseroot)[-2:]

    unlock_file("env_case.xml",caseroot=caseroot)
    casename = basecasename+"."+date+"."+member
    case.set_value("CASE",casename)
    case.flush()
    lock_file("env_case.xml",caseroot=caseroot)

    case.set_value("CONTINUE_RUN",False)
    case.set_value("RUN_REFDATE",date)
    case.set_value("RUN_STARTDATE",date)
    case.set_value("RUN_REFDIR",sdrestdir)
    case.set_value("REST_OPTION",'none')
    case.set_value("PROJECT","NCGD0047")
    case.set_value("OCN_TRACER_MODULES","iage cfc ecosys")
#    dout_s_root = case.get_value("DOUT_S_ROOT")
#    dout_s_root = os.path.join(os.path.dirname(dout_s_root),casename)
#    if dout_s_root.startswith("/glade/scratch"):
#        dout_s_root = dout_s_root.replace("/glade/scratch/","/glade/p/nsc/ncgd0042/")
#    case.set_value("DOUT_S_ROOT",dout_s_root)
    # restage user_nl files for each run
    for usermod in glob.iglob(user_mods_dir+"/user*"):
        safe_copy(usermod, caseroot)

    case.case_setup()

    stage_refcase(rundir, sdrestdir, date, basecasename)
    case.set_value("BATCH_SYSTEM", "none")
    safe_copy(os.path.join(caseroot,"env_batch.xml"),os.path.join(caseroot,"LockedFiles","env_batch.xml"))
    # this doesnt appear to work correctly
#    unlock_file("env_batch.xml",caseroot=caseroot)
#    case.flush()
#    lock_file("env_batch.xml",caseroot=caseroot)


def build_base_case(date, baseroot, basecasename, basemonth,res, compset, overwrite,
                    sdrestdir, user_mods_dir, pecount=None):
    caseroot = os.path.join(baseroot,basecasename+"."+date[:7]+".001")
    #caseroot = os.path.join(baseroot,basecasename+".{}".format(date[:7])+".00")
    if overwrite and os.path.isdir(caseroot):
        shutil.rmtree(caseroot)
            
    with Case(caseroot, read_only=False) as case:
        if not os.path.isdir(caseroot):
            case.create(os.path.basename(caseroot), cesmroot, compset, res,
                        run_unsupported=True, answer="r",walltime="12:00:00",
                        user_mods_dir=user_mods_dir, pecount=pecount, project="NCGD0047")
            # make sure that changing the casename will not affect these variables
            case.set_value("EXEROOT",case.get_value("EXEROOT", resolved=True))
            case.set_value("CIME_OUTPUT_ROOT","/glade/scratch/$USER/SMYLE")
            case.set_value("RUNDIR",case.get_value("RUNDIR",resolved=True)+".01")

            case.set_value("RUN_TYPE","hybrid")
            case.set_value("GET_REFCASE",False)
            case.set_value("RUN_REFDIR",sdrestdir)
            case.set_value("RUN_REFCASE", "b.e21.SMYLE_IC.f09_g17.{}.01".format(date[:7]))
            case.set_value("OCN_TRACER_MODULES","")
            case.set_value("OCN_TRACER_MODULES","iage")
            case.set_value("OCN_CHL_TYPE","diagnostic")
            case.set_value("NTHRDS", 1)
            # pelayout for cesm2cam6 case
#            case.set_value("NTASKS_ATM",1152)
#            case.set_value("NTASKS_CPL",1152)
#            case.set_value("NTASKS_LND",1044)
#            case.set_value("NTASKS_ROF",1044)
#            case.set_value("NTASKS_ICE", 108)
#            case.set_value("NTASKS_OCN",  54)
#            case.set_value("NTASKS_WAV",  18)
#            case.set_value("ROOTPE_ICE",1044)
#            case.set_value("ROOTPE_OCN",1152)
#            case.set_value("ROOTPE_WAV",1206)


            case.set_value("STOP_OPTION","nmonths")
            case.set_value("STOP_N", 24)
            case.set_value("REST_OPTION","none")
            
            case.set_value("CCSM_BGC","CO2A")
            case.set_value("EXTERNAL_WORKFLOW",True)
            case.set_value("CLM_NAMELIST_OPTS", "use_init_interp=.true.")

        rundir = case.get_value("RUNDIR")
        per_run_case_updates(case, date, sdrestdir, user_mods_dir, rundir)
        #build.case_build(caseroot, case=case)

        return caseroot

def clone_base_case(date, caseroot, ensemble, sdrestdir, user_mods_dir, overwrite):

    startval = "02"
    nint = len(startval)
    cloneroot = caseroot
    for i in range(int(startval), int(startval)+ensemble):
        member_string = '{{0:0{0:d}d}}'.format(nint).format(i)
        if ensemble > 1:
            caseroot = caseroot[:-nint] + member_string
        if overwrite and os.path.isdir(caseroot):
            shutil.rmtree(caseroot)
        if not os.path.isdir(caseroot):
            with Case(cloneroot, read_only=False) as clone:
                clone.create_clone(caseroot, keepexe=True,
                                   user_mods_dir=user_mods_dir)
        with Case(caseroot, read_only=True) as case:
            # rundir is initially 00 reset to current member
            rundir = case.get_value("RUNDIR")
            rundir = rundir[:-nint]+member_string
            case.set_value("RUNDIR",rundir)
            per_run_case_updates(case, date, sdrestdir, user_mods_dir, rundir)

def _main_func(description):
    #date, basecasename = parse_command_line(sys.argv, description)
    date, model = parse_command_line(sys.argv, description)
    basecasename = "b.e21.SMYLE.f09_g17"

    # TODO make these input vars

    basemonth = int(date[5:7])
    baseyear = int(date[0:4])
    baseroot = os.path.join(os.getenv("WORK"),"CESM2-SMYLE","cases")
    #usecase  = os.getenv("USECASE")
    #baseroot = os.path.join(os.getenv("WORK"),"CESM2-SMYLE","cases",basecasename)
    res = "f09_g17"
    waccm = False
    if model == "cesm2smyle":
        if baseyear < 2014 or (baseyear == 2014 and basemonth < 10):
            compset = "BSMYLE"
        else:
            compset = "BSMYLESSP370"
        
    print ("baseyear is {} basemonth is {}".format(baseyear,basemonth))
    
    overwrite = True
    #sdrestdir = os.path.join(os.getenv("SCRATCH"),"SMYLE","inputdata","cesm2_init","b.e21.SMYLE_IC.f09_g16","{}".format(date))
    #sdrestdir = os.path.join("/glade/scratch/nanr","SMYLE","inputdata","cesm2_init","b.e21.SMYLE_IC.f09_g16","1958")
    sdrestdir = os.path.join(os.getenv("SCRATCH"),"SMYLE","inputdata","cesm2_init","b.e21.SMYLE_IC.f09_g17."+date[0:7]+".01","{}".format(date))
    baserundir = os.path.join(os.getenv("SCRATCH"),"SMYLE","rundir","b.e21.SMYLE.f09_g17."+date[0:7]+".001","run.01")
    ensemble = 4

    #user_mods_dir = os.path.join(s2sfcstroot,"user_mods",basecasename)
    user_mods_dir = os.path.join(s2sfcstroot,"user_mods","cesm2smyle")

    # END TODO
    print("basemonth = {}".format(basemonth))
    caseroot = build_base_case(date, baseroot, basecasename, basemonth, res,
                            compset, overwrite, sdrestdir, user_mods_dir+'.base', pecount="S")
    clone_base_case(date, caseroot, ensemble, sdrestdir, user_mods_dir, overwrite)

if __name__ == "__main__":
    _main_func(__doc__)
