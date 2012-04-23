"""
| Copyright (C) 2007-2012 Philip Axer, Jonas DIemer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer
         - Jonas Diemer

Description
-----------

Static Priority Preemptive (SPP) busy window in various flavours 
"""

import logging
import analysis

def spp_multi_activation_stopping_condition(task, q, w):
    """ Check if we have looked far enough
        Returns True if stopping-condition is satisfied, False otherwise 
    """

    # if there are no new activations when the current busy period has been completed, we terminate
    if task.in_event_model.delta_min(q + 1) >= w:
        return True
    return False

def w_spp(task, q, MAX_WINDOW=1000, **kwargs):
    """ Return the maximum time required to process q activations
        Priority stored in task.scheduling_parameter
        smaller priority number -> right of way
        Policy for equal priority is FCFS (i.e. max. interference).
        This corresponds to Theorem 1 in [Lehoczky1990]_ or Equation 2.3 in [Richter2005]_.
    """
    assert(task.scheduling_parameter != None)
    assert(task.wcet >= 0)

    w = q * task.wcet

    while True:
        #logging.debug("w: %d", w)
        #logging.debug("e: %d", q * task.wcet)
        s = 0
        #logging.debug(task.name+" interferers "+ str([i.name for i in task.get_resource_interferers()]))
        for ti in task.get_resource_interferers():
            assert(ti.scheduling_parameter != None)
            assert(ti.resource == task.resource)
            if ti.scheduling_parameter <= task.scheduling_parameter: # equal priority also interferes (FCFS)
                s += ti.wcet * ti.in_event_model.eta_plus(w)
                #logging.debug("e: %s %d x %d", ti.name, ti.wcet, ti.in_event_model.eta_plus(w))

        w_new = q * task.wcet + s
        #print ("w_new: ", w_new)
        if w == w_new:
            break
        w = w_new

    assert(w >= q * task.wcet)
    return w

def w_spp_domination(task, q, MAX_WINDOW=1000):
    """ Return the maximum time required to process q activations
        Priority stored in task.scheduling_parameter
        smaller priority number -> right of way
        Policy for equal priority is total dominiation (i.e. no interference from other tasks)
    """
    assert(task.scheduling_parameter != None)
    assert(task.wcet >= 0)

    w = q * task.wcet

    while True:
        #logging.debug("w: %d", w)
        #logging.debug("e: %d", q * task.wcet)
        s = 0
        #logging.debug(task.name+" interferers "+ str([i.name for i in task.get_resource_interferers()]))
        for ti in task.get_resource_interferers():
            assert(ti.scheduling_parameter != None)
            assert(ti.resource == task.resource)
            if ti.scheduling_parameter < task.scheduling_parameter: # equal priority also interferes (FCFS)
                s += ti.wcet * ti.in_event_model.eta_plus(w)
                #logging.debug("e: %s %d x %d", ti.name, ti.wcet, ti.in_event_model.eta_plus(w))

        w_new = q * task.wcet + s
        #print ("w_new: ", w_new)
        if w == w_new:
            break
        w = w_new

    assert(w >= q * task.wcet)
    return w

def w_spp_roundrobin(task, q, MAX_WINDOW=1000):
    """ Return the maximum time required to process q activations
        Priority stored in task.scheduling_parameter
        smaller priority number -> right of way
        Policy for equal priority is non-preemptive Round-Robin (i.e. without slot times) 
    """
    assert(task.scheduling_parameter != None)
    assert(task.wcet >= 0)

    w = q * task.wcet
    while True:
        #logging.debug("w: %d", w)
        #logging.debug("e: %d", q * task.wcet)
        s = 0
        #logging.debug(task.name+" interferers "+ str([i.name for i in task.get_resource_interferers()]))
        for ti in task.get_resource_interferers():
            assert(ti.scheduling_parameter != None)
            assert(ti.resource == task.resource)
            if ti.scheduling_parameter < task.scheduling_parameter: # lower priority number -> block
                s += ti.wcet * ti.in_event_model.eta_plus(w)
                #logging.debug("e: %s %d x %d", ti.name, ti.wcet, ti.in_event_model.eta_plus(w))
            if ti.scheduling_parameter == task.scheduling_parameter: # equal priority -> round robin
                # assume cooperative round-robin                
                s += ti.wcet * min(q, ti.in_event_model.eta_plus(w))

        w_new = q * task.wcet + s
        #print ("w_new: ", w_new)
        if w == w_new:
            break
        w = w_new

    assert(w >= q * task.wcet)
    return w

