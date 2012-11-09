'''
invoke_process.py -- launch multiple subprocesses, each running smf_invocation instance
Copyright 2012 -- Ben England
Licensed under the Apache License at http://www.apache.org/licenses/LICENSE-2.0
See Appendix on this page for instructions pertaining to license.
'''

import multiprocessing
import unittest
import smallfile
import os
import time

OK = 0  # system call return code for success

# this class is used to launch multiple threads with smf_invocation instances
# we do this because we can use > 1 core this way, with 
# python threading, it doesn't really use > 1 core because of the GIL (global lock)
# occasional status reports can be sent back using pipe as well

class subprocess(multiprocessing.Process):
    def __init__(self, invocation):
        multiprocessing.Process.__init__(self)
        (conn1, conn2) = multiprocessing.Pipe(False)
        self.receiver = conn1            # master process receives data on results of test here
        self.sender = conn2              # slave process sends data on results of test here
        self.invoke = invocation         # all the workload generation is done by this object

    def run(self):
        try:
          self.invoke.do_workload()
          self.invoke.log.debug('exiting subprocess and returning invoke '+ str(self.invoke))
        except Exception as e:
          print 'Exception seen in thread %s (tail %s%sinvoke_logs_%s.log) '%\
                        (self.invoke.tid, self.invoke.tmp_dir, os.sep, self.invoke.tid)
          self.invoke.log.error(str(e))
          self.status = self.invoke.NOTOK
        finally:
          self.rsptimes = None # response time array should have been saved to file first
          self.invoke.log = None # log objects cannot be serialized
          self.sender.send(self.invoke)

# below are unit tests for smf_invocation
# including multi-threaded test
# to run, just do "python invoke_process.py"

ok=0
class Test(unittest.TestCase):
    def setUp(self):
        self.invok = smallfile.smf_invocation()
        self.invok.debug = True
        self.invok.verbose = True
        self.invok.tid = "regtest"
        self.invok.start_log()

    def deltree(self):
        if not os.path.exists(self.invok.top_dir): return
        if not os.path.isdir(self.invok.top_dir): return
        for (dir, subdirs, files) in os.walk(self.invok.top_dir, topdown=False):
            for f in files: os.unlink(os.path.join(dir,f))
            for d in subdirs: os.rmdir(os.path.join(dir,d))
        os.rmdir(self.invok.top_dir)
        
    def test_multiproc_stonewall(self):
        self.invok.log.info('starting stonewall test')
        thread_ready_timeout = 4
        thread_count = 4
        self.deltree()
        os.mkdir(self.invok.top_dir)
        os.mkdir(self.invok.src_dir)
        os.mkdir(self.invok.dest_dir)
        os.mkdir(self.invok.network_dir)
        self.invok.starting_gate = os.path.join(self.invok.network_dir, 'starting-gate')
        sgate_file = self.invok.starting_gate
        invokeList = []
        for j in range(0, thread_count):
            s = smallfile.smf_invocation()
            #s.log_to_stderr = True
            s.verbose = True
            s.tid = str(j)
            s.prefix = "thr_"
            s.suffix = "foo"
            s.iterations=10
            s.stonewall = False
            s.starting_gate = sgate_file
            invokeList.append(s)
        threadList=[]
        for s in invokeList: threadList.append(subprocess(s))
        for t in threadList: t.start()
        threads_ready = True
        for i in range(0, thread_ready_timeout):
            threads_ready = True
            for s in invokeList:
                thread_ready_file = s.gen_thread_ready_fname(s.tid)
                if not os.access(thread_ready_file, os.R_OK): threads_ready = False
            if threads_ready: break
            time.sleep(1)
        if not threads_ready: raise Exception("threads did not show up within %d seconds"%thread_ready_timeout)
        time.sleep(1)
        f = open(sgate_file, "w")
        f.close()
        for t in threadList: 
            rtnd_invok = t.receiver.recv()
            t.join()
            self.invok.log.info(str(rtnd_invok))
            if rtnd_invok.status != ok:
                raise Exception("subprocess failure: " + str(t))


# so you can just do "python invoke_process.py" to test it

if __name__ == "__main__":
    unittest.main()
