'''Tests the test suite and pulsar distribution.'''
import os
import threading
import multiprocessing

import pulsar
from pulsar.utils.test import test

class TestTestWorker(test.TestCase):
    
    def testWorker(self):
        worker = pulsar.get_actor()
        self.assertTrue(pulsar.is_actor(worker))
        self.assertTrue(worker.running())
        self.assertFalse(worker.closed())
        self.assertFalse(worker.stopped())
        self.assertEqual(worker.state, 'running')
        self.assertEqual(worker.tid, threading.current_thread().ident)
        if worker.isprocess():
            self.assertEqual(worker.pid, os.getpid())
        self.assertTrue(worker.cpubound)
        
    def testMailbox(self):
        worker = self.worker
        mailbox = worker.mailbox
        self.assertTrue(mailbox)
        self.assertTrue(mailbox.ioloop)
        self.assertTrue(mailbox.ioloop.running())
        self.assertNotEqual(worker.requestloop, mailbox.ioloop)
        self.assertNotEqual(worker.tid, mailbox.ioloop.tid)
        self.assertTrue(mailbox.address)
        self.assertTrue(mailbox.sock)
        
    def testIOloop(self):
        worker = pulsar.get_actor()
        ioloop = pulsar.thread_ioloop()
        self.assertTrue(ioloop.running())
        self.assertNotEqual(worker.requestloop, ioloop)
        self.assertEqual(worker.ioloop, ioloop)
        self.assertEqual(worker.tid, worker.requestloop.tid)
        self.assertNotEqual(worker.tid, ioloop.tid)
        self.assertTrue(str(ioloop))
        self.assertFalse(ioloop.start())
        
    def testThreadInfo(self):
        worker = self.worker
        actor = pulsar.get_actor()
        self.assertEqual(actor,worker)
        ct = threading.current_thread()
        self.assertEqual(ct.actor,worker)
        

class TestPulsar(test.TestCase):
    
    def test_version(self):
        self.assertTrue(pulsar.VERSION)
        self.assertTrue(pulsar.__version__)
        self.assertEqual(pulsar.__version__,pulsar.get_version(pulsar.VERSION))
        self.assertTrue(len(pulsar.VERSION) >= 2)

    def test_meta(self):
        for m in ("__author__", "__contact__", "__homepage__", "__doc__"):
            self.assertTrue(getattr(pulsar, m, None))