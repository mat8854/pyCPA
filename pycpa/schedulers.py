"""
| Copyright (C) 2012 Philip Axer, Jonas Diemer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Jonas Diemer, Philip Axer

Description
-----------

Local analysis functions (schedulers)
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import itertools
import math
import logging

from . import analysis
from . import options

logger = logging.getLogger("pycpa")

EPSILON = 1e-9

# priority orderings
prio_high_wins_equal_fifo = lambda a, b : a >= b
prio_low_wins_equal_fifo = lambda a, b : a <= b
prio_high_wins_equal_domination = lambda a, b : a > b
prio_low_wins_equal_domination = lambda a, b : a < b


class TrivialFIFOScheduler(analysis.Scheduler):
    """ Trivial FIFO Scheduler
    The trivial scheduler assums all activations in the
    busy window could block the task. This cannot happen in reality.

    See :class:`pycpa.schedulers.FIFOScheduler`.
    """


    def __init__(self):
        analysis.Scheduler.__init__(self)

    def b_plus(self, task, q, details=None):
        """ Returns the largest time interval to process q activation,
        assuming they all arrive in the same busy window.

        """
        assert(task.wcet >= 0)

        w = q * task.wcet

        while True:
            # logging.debug("w: %d", w)
            # logging.debug("e: %d", q * task.wcet)
            s = 0
            # logging.debug(task.name+" interferers "+ str([i.name for i in task.get_resource_interferers()]))
            for ti in task.get_resource_interferers():
                    s += ti.wcet * ti.in_event_model.eta_plus(w)
                    # logging.debug("e: %s %d x %d", ti.name, ti.wcet, ti.in_event_model.eta_plus(w))

            w_new = q * task.wcet + s
            # print ("w_new: ", w_new)
            if w == w_new:
                assert(w >= q * task.wcet)
                if details is not None:
                    details['q*WCET'] = str(q) + '*' + str(task.wcet) + '=' + str(q * task.wcet)
                    for ti in task.get_resource_interferers():
                            details[str(ti) + ':eta*WCET'] = str(ti.in_event_model.eta_plus(w)) + '*'\
                                + str(ti.wcet) + '=' + str(ti.wcet * ti.in_event_model.eta_plus(w))
                return w

            w = w_new

class FIFOScheduler(analysis.Scheduler):
    """ FIFO Scheduler

    This is a candidate-based FIFO scheduling analysis.
    """

    def __init__(self):
        analysis.Scheduler.__init__(self)

    def compute_wcrt(self, task, task_results):
        """ Compute the worst-case response time of Task

        :param task: the analyzed task
        :type task: model.Task
        :param task_results: dictionary which stores analysis results
        :type task_results: dict (analysis.TaskResult)
        :rtype: integer (worst-case response time)

        """

        max_iterations = options.get_opt('max_iterations')
        details = dict()

        max_wcrt = 0
        q_wcrt = 0
        task_results[task].busy_times = [0]  # busy time of 0 activations
        q = 1
        while True:

            if q == max_iterations:
                logger.error(
                    "max_iterations reached, tasks (likely) not schedulable!")
                # raise NameError("max_iterations reached, tasks (likely) not
                # schedulable!")
                raise NotSchedulableException("max_iterations for %s reached, "
                                              "tasks (likely) not schedulable!"
                                              % task.name)

            if task.in_event_model.delta_min(q) >= self.q_plus(task, q):
                break
            b_plus = self.b_plus(task,q)
            task_results[task].busy_times.append(b_plus)

            current_response = self.__wcrt_candidate(task, q)
            if current_response > max_wcrt:
                max_wcrt = current_response
                q_wcrt = q
            q += 1

        task_results[task].q_wcrt = q_wcrt
        task_results[task].wcrt = max_wcrt
        task_results[task].b_wcrt = self.__wcrt_candidate(task, q_wcrt, details=True)

        return task_results

    def __b_plus_candidate(self, task, q, release_time):
        """ Returns the multiple event busy time of q events of the given task
        assuming they all arrive in the same busy window and the very
        first event arrives at release_time.
        """
        # window initialized to the first activation
        w = release_time
        for qi in range(1, q+1):
            # first, we check in which interval a
            # following activation qi could arrive in, without ending the
            # busy window.
            w = self.__q_plus_candidate(task, qi, release_time)
            # for the next event we pick the latest possible release time
            # so the event doesn't fall outside the busy window
            release_time = w
        return w + task.wcet

    def __q_plus_candidate(self, task, q, release_time):
        """ Returns the queuing delay of the q-th activation
        assuming its earliest release time is release_time """
        w = task.wcet*(q-1)
        for ti in task.get_resource_interferers():
            w += ti.in_event_model.eta_plus_closed(release_time)
        return w

    def __get_candidates_in_window(self, task, w):
        """ Returns a set of candidate release times in the window w """

        candidates = set()
        for ti in task.get_resource_interferers():
            q_max = ti.in_event_model.eta_plus(w)
            candidates.update([ti.in_event_model.delta_min(q) for q in range(1, q_max+1)])
        return candidates

    def q_plus(self, task, q, details=False):
        """ Returns the largest time interval from the arrival of
        the first activation until the q-th activation is admitted
        service, assuming all q events arrive in the same busy window
        """

        return self.b_plus(task, q) - task.wcet

    def b_plus(self, task, q, details=False):
        """ Returns the largest time interval from the arrival of
        the first until the finishing of the q-th event,
        assuming all q activations arrive in the same busy window
        """
        candidates_checked = set()
        candidates_outstanding = set([0])

        release_time = 0
        b_max = 0
        w_max = 0
        a = 0

        while len(candidates_outstanding) > 0:
            release_time = candidates_outstanding.pop()
            candidates_checked.add(release_time)

            w = self.__b_plus_candidate(task, q, release_time)
            candidates_outstanding.update(self.__get_candidates_in_window(task,w) - candidates_checked)
            b_new = w - release_time
            if b_new > b_max:
                b_max = b_new
                w_max = w
                a = release_time

        if details:
            details_dict = dict()
            details_dict['release time'] = a
            details_dict['total window'] = w_max
            details_dict['busy time'] = b_max
            return details_dict

        return b_max

    def __wcrt_candidate(self, task, q, details=False):
        candidates_checked = set()
        candidates_outstanding = set([0])

        release_time = 0
        wcrt_max = 0
        w_max = 0
        a = 0
        while len(candidates_outstanding) > 0:
            release_time = candidates_outstanding.pop()
            candidates_checked.add(release_time)

            w = self.__q_plus_candidate(task, q, release_time) + task.wcet
            candidates_outstanding.update(self.__get_candidates_in_window(task,w) - candidates_checked)
            wcrt_new  = w - release_time
            if wcrt_new > wcrt_max:
                wcrt_max = wcrt_new
                a = release_time
                w_max = w

        if details:
            details_dict = dict()
            details_dict['release time'] = a
            details_dict['total window'] = w_max
            details_dict['wcrt'] = wcrt_max
            return details_dict
        return wcrt_max


class EDFPScheduler(analysis.Scheduler):
    """ Earliest-Deadline-First-Preemptive Scheduler

    local deadlines must be stored in task.deadline

    Policy for coinciding deadlines is max. interference.

    .. warning::
        experimental, use with caution

    """

    def edf_busy_period(self, task):
        """ Returns the max. time, the resource is busy

        :param task: the analyzed task
        :type task: model.Task
        :rtype: integer (max. time)
        """

        w = task.wcet

        while True:
            w_new = 0
            for ti in (task.get_resource_interferers() | set([task])):
                w_new += ti.wcet * ti.in_event_model.eta_plus(w)

            if w == w_new:
                break
            w = w_new
        return w


    def _activation_time_candidates(self, task, q):
        """ Returns a set of activation times which must be evaluated.

        similar to [Palencia1998]_ Equation 10 and 15

        :param task: the analyzed task
        :type task: model.Task
        :param q: the index of the activation for which candidates are evaluated
        :type q: integer
        :rtype: set of integers
        """
        busy_period = self.edf_busy_period(task)
        # print "busy_period", busy_period

        # will contain all deadlines of all
        # resource interferers in the busy period
        candidate_deadlines = list([task.deadline])

        for ti in task.get_resource_interferers():

            n = ti.in_event_model.eta_plus(busy_period)  # amount of activations of ti in the busy period
            # print "name:", ti.name, "n:", "range:", range(1, n + 1)
            ti_deadlines = [ti.in_event_model.delta_min(p) + ti.deadline for p in range(1, n + 1)]  # instances of deadlines for ti
            # print "ti_deadlines", ti_deadlines
            candidate_deadlines.extend(ti_deadlines)
        # print "deadlines", candidate_deadlines
        # calculate the activation instances so that the deadlines of task and the tis match

        candidate_activations = set()
        for di in candidate_deadlines:
            ac = max(0, di - task.deadline)
            # if ((ac - task.in_event_model.delta_min(q) >= 0) and
            #   (ac <= busy_period - task.wcet)): # the arrival of the first event must be in the busy window
            if ((ac >= task.in_event_model.delta_min(q)) and
               (ac < task.in_event_model.delta_min(q + 1))):  # the arrival of the first event must be in the busy window
                candidate_activations.add(ac)

        return candidate_activations

    def _eta_activation_time(self, task, q, ti, w, activation_time):
        """ Returns the number of interference activations orginating from task ti
        which is seen during the execution of q activations of task,
        assuming the q-th activation was released at activation_time.

        similar to [Palencia2003]_ Equation 9

        :param task: the analyzed task
        :type task: model.Task
        :param q: the amount of activations for task
        :type q: integer
        :param ti: interference task
        :type ti: model.Task
        :param w: busy window length
        :type w: integer
        :param activation_time: activation time (relative to the busy window start!)
        :type activation_time: integer
        :rtype: amount of activations as integer
        """

        # all activations in the current window
        n_ti = ti.in_event_model.eta_plus(w)

        deadline_task = activation_time + task.deadline

        # all activations which have a deadline before tasks's deadline (and thus have a higher priority)
        n_before_deadline = ti.in_event_model.eta_plus_closed(deadline_task - ti.deadline)
        # print "ti: ", ti.name, "n_ti", n_ti, "n_before_deadline", n_before_deadline, "w_deadline", deadline_task - ti.deadline + EPSILON
        eta = min(n_ti, n_before_deadline)
        return max(0, eta)

    def _window_candidate(self, task, q, activation_time):
        w = q * task.wcet
        # print "candidate activation_time:", activation_time
        while True:
            # print " - w:", w
            # logging.debug("e: %d", q * task.wcet)
            s = 0
            # logging.debug(task.name+" interferers "+ str([i.name for i in task.get_resource_interferers()]))
            for ti in task.get_resource_interferers():
                eta = self._eta_activation_time(task, q, ti, w, activation_time)
                # print " - ti", ti.name, "eta", eta
                s += ti.wcet * eta

            w_new = q * task.wcet + s
            # print ("w_new: ", w_new)
            if w == w_new:
                break
            w = w_new

        assert(w >= q * task.wcet)
        return w


    def b_plus(self, task, q, details=None):
        """ time required to process q subsequent activations of task

        :param task: the analyzed task
        :type task: model.Task
        :param q: the amount of activations for task
        :type q: integer
        :rtype: integer
        """
        assert(task.deadline != None)
        assert(task.wcet >= 0)

        activation_candidates = self._activation_time_candidates(task, q)
        # print "amount of candidates:", activation_candidates
        w = 0
        a = 0
        for ac in activation_candidates:
            w_new = self._window_candidate(task, q, ac) - ac + task.in_event_model.delta_min(q)
            # print "  -> window_candidate:", w_new
            w_new = w_new
            if w_new > w:
                w = w_new
                a = ac

        # print "  -----> w_max:", w, "ac:", a
        if details is not None:
            # TODO: implement details==True
            return dict()
        else:
            return w


    def stopping_condition(self, task, q, w):
        """ Return true if a sufficient number of activations q have been evaluated
        for a task during the busy-time w under EDF scheduling.

        :param task: the analyzed task
        :type task: model.Task
        :param q: the number of activations
        :type q: integer
        :param w: the current busy-time
        :type w: integer
        :rtype: integer (max. busy-time for q activations)
        """

        if task.in_event_model.delta_min(q + 1) >= self.edf_busy_period(task):
            return True
        return False


class RoundRobinScheduler(analysis.Scheduler):
    """ Round-Robin Scheduler

    task.scheduling_parameter is the respective slot size
    """

    def b_plus(self, task, q, details=None):
        w = q * task.wcet
        # print "q=",q
        while True:
            s = 0
            for ti in task.get_resource_interferers():
                # print "sum+=min(",q,",",ti.in_event_model.eta_plus(w)
                # s += min(q, ti.eta_plus(w))
                if hasattr(task, "scheduling_parameter") and task.scheduling_parameter is not None:
                    s += min(int(math.ceil(float(q) * task.wcet / task.scheduling_parameter)) * ti.scheduling_parameter,
                         ti.in_event_model.eta_plus(w) * ti.wcet)
                else:
                    # Assume cooperative round robin
                    s += ti.wcet * min(q, ti.in_event_model.eta_plus(w))

            # print "w=",q,"+",sum, ", eta_plus(w)=", task.in_event_model.eta_plus(q+sum)
            w_new = q * task.wcet + s

            if w == w_new:
                if details is not None:
                    details['q*WCET'] = str(q) + '*' + str(task.wcet) + '=' + str(q * task.wcet)

                    for ti in task.get_resource_interferers():
                        if hasattr(task, "scheduling_parameter") and task.scheduling_parameter is not None:
                            if int(math.ceil(float(q) * task.wcet / task.scheduling_parameter)) * ti.scheduling_parameter < ti.in_event_model.eta_plus(w) * ti.wcet:
                                details[str(ti)] = '%d*%d' % \
                                    (int(math.ceil(float(q) * task.wcet / task.scheduling_parameter)),
                                     ti.scheduling_parameter)
                            else:
                                details[str(ti)] = '%d*%d' % (ti.in_event_model.eta_plus(w), ti.wcet)
                        else:
                            details[str(ti)] = "%d*min(%d,%d)=%d*%d" % \
                                (ti.wcet, q, ti.in_event_model.eta_plus(w),
                                 ti.wcet, min(q, ti.in_event_model.eta_plus(w)))
                return w
            w = w_new


class SPNPScheduler(analysis.Scheduler):
    """ Static-Priority-Non-Preemptive Scheduler

    Priority is stored in task.scheduling_parameter,
    by default numerically lower numbers have a higher priority

    Policy for equal priority is FCFS (i.e. max. interference).
    """

    def __init__(self, priority_cmp=prio_low_wins_equal_fifo, ctx_switch_overhead=0, cycle_time=EPSILON):
        """
        :param priority_cmp: function to evaluate priority comparison of the form foo(a,b). if foo(a,b) == True, then "a" is more important than "b"
        :param cycle_time: time granularity of the scheduler, see [Bate1998]_ E.q. 4.14
        :param ctx_switch_overhead: context switching overhead (or interframe space for transmission lines)
        """
        analysis.Scheduler.__init__(self)

        # # time granularity of the scheduler
        self.cycle_time = cycle_time

        # # Context-switch overhead
        self.ctx_switch_overhead = ctx_switch_overhead

        # # priority ordering
        self.priority_cmp = priority_cmp

    def _blocker(self, task):
        # find maximum lower priority blocker
        b = 0
        for ti in task.get_resource_interferers():
            if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter) == False:
                b = max(b, ti.wcet)
        return b

    def spnp_busy_period(self, task):
        """ Calculated the busy period of the current task
        """
        b = self._blocker(task) + self.ctx_switch_overhead
        w = b

        while True:
            w_new = b
            for ti in task.get_resource_interferers() | set([task]):
                if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter) or (ti == task):
                    w_new += (ti.wcet + self.ctx_switch_overhead) * ti.in_event_model.eta_plus(w)

            if w == w_new:
                break

            w = w_new

        return w

    def stopping_condition(self, task, q, w):
        """ Check if we have looked far enough
            compute the time the resource is busy processing q activations of task
            and activations of all higher priority tasks during that time
            Returns True if stopping-condition is satisfied, False otherwise
        """

        # if there are no new activations when the current busy period has been completed, we terminate
        if task.in_event_model.delta_min(q + 1) >= self.spnp_busy_period(task):
            return True
        return False


    def b_plus(self, task, q, details=None):
        """ Return the maximum time required to process q activations
        """
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        b = self._blocker(task) + self.ctx_switch_overhead

        w = (q - 1) * (task.wcet + self.ctx_switch_overhead) + b

        while True:
            # logging.debug("w: %d", w)
            # logging.debug("e: %d", q * task.wcet)
            s = 0
            # logging.debug(task.name+" interferers "+ str([i.name for i in task.get_resource_interferers()]))
            for ti in task.get_resource_interferers():
                assert(ti.scheduling_parameter != None)
                assert(ti.resource == task.resource)
                if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter):  # equal priority also interferes (FCFS)
                    s += (ti.wcet + self.ctx_switch_overhead) * ti.in_event_model.eta_plus(w + self.cycle_time)
                    # logging.debug("e: %s %d x %d", ti.name, ti.wcet, ti.in_event_model.eta_plus(w))

            w_new = (q - 1) * (task.wcet + self.ctx_switch_overhead) + b + s
            # print ("w_new: ", w_new)
            if w == w_new:

                if details is not None:
                    details['q*WCET'] = str(q) + '*' + str(task.wcet) + '=' + str(q * task.wcet)
                    details['blocker'] = str(b)
                    for ti in task.get_resource_interferers():
                        if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter):
                            details[str(ti) + ':eta*WCET'] = str(ti.in_event_model.eta_plus(w + self.cycle_time)) + '*'\
                                + str(ti.wcet) + '=' + str((ti.wcet + self.ctx_switch_overhead) * ti.in_event_model.eta_plus(w + self.cycle_time))
                w += task.wcet
                assert(w >= q * task.wcet)
                return w
            w = w_new


class SPPOffsetScheduler(analysis.Scheduler):
    """ Static-Priority-Preemptive Scheduler
    with offset support.

    This is currently untested.
    Formulars are implemented according to [Palencia1998]_
    """

    def stopping_condition(self, task, q, w):
        # TODO: Check!!!
        return analysis.Scheduler.stopping_condition(self, task, q, w)


    def calculate_candidates(self, task):
        """
            Identifies the transactions on the local component, by looking at the event streams.
            Then it itentifies possible candidate tasks per stream and calculates the
            cartesian product which is used for determining the worst case
        """
        logger.debug("calculate_candidates %s", task.name)
        tasks_in_transaction = dict()
        transactions = set()

        tasks_in_transaction[task.path] = [i for i in task.path.tasks if i.resource == task.resource and  i.scheduling_parameter < task.scheduling_parameter]
        tasks_in_transaction[task.path].append(task)
        transactions.add(task.path)

        for ti in task.get_resource_interferers():
            if ti.scheduling_parameter < task.scheduling_parameter:
                tasks = [i for i in ti.path.tasks if i.resource == task.resource]
                if len(tasks) > 0:
                    tasks_in_transaction[ti.path] = tasks
                    transactions.add(ti.path)

        for trans in transactions:
            logger.debug("identified the following transaction %s ntasks: %d ", trans, len(tasks_in_transaction[trans]))


        candidates = list()
        for element in itertools.product(*(tasks_in_transaction.values())):
            candidates.append(element)

        logger.debug("transactions: %d", len(transactions))
        logger.debug("num cands: %d", len(candidates))

        return tasks_in_transaction, candidates

    def phi_ijk(self, task_ij, task_ik):
        """ Phase between task task_ij and the critical instant initiated with task_ik
            Eq. 17 Palencia2002
        """

        # T_i= task_ij.min_average_between_two_events()
        T_i = task_ij.in_event_model.P
        assert T_i > 0

        phi_ik = task_ik.in_event_model.phi
        phi_ij = task_ij.in_event_model.phi
        J_ik = task_ik.in_event_model.J

        return T_i - (phi_ik + J_ik - phi_ij) % T_i

    def transaction_contribution(self, tasks_in_transaction, task_ik, task, t):
        w = 0
        T_i = task_ik.in_event_model.P
        assert(T_i > 0)
        for ti in tasks_in_transaction:
            # The period (T_i) for all tasks in the transaction is the same
            assert task_ik.in_event_model.P == ti.in_event_model.P
            J_ij = ti.in_event_model.J
            phi = self.phi_ijk(ti, task_ik)
            # print "phi", phi
            # print "T_i", T_i
            # print "t", t
            n = math.floor((float(J_ij + phi)) / T_i) + math.ceil((float(t - phi) / float(T_i)))
            # print "n", n
            w += n * ti.wcet
        return w

    def w_spp_candidate(self, tasks_in_transaction, task, candidate, q):

        # initiator of the critical instant for the transaction of task
        va = [x for x in candidate if task.path == x.path][0]
        T = task.in_event_model.P

        w = float(task.wcet)

        while True:
            # print "---------------------"
            # print "phi_ijk(task, va)", phi_ijk(task, va)
            w_new = (q + math.floor((task.in_event_model.J + self.phi_ijk(task, va)) / float(T))) * task.wcet
            logger.debug("   w_new: %f", w_new)
            # print "w_new", w_new
            for i in candidate:
                if i == task:
                    continue
                w_trans = self.transaction_contribution(tasks_in_transaction[i.path], i, task, w)
                logger.debug("   w_trans: %f", w_trans)
                # print "w_trans", w_trans
                w_new += w_trans
            if w_new == w:
                break
            w = w_new

        # w += task.in_event_model.phi - phi_ijk(task, va) + task.in_event_model.P
        w += -1 * self.phi_ijk(task, va) + task.in_event_model.P - task.in_event_model.J

        assert w >= task.wcet

        return w



    def b_plus(self, task, q, details=None):
        """ Return the maximum time required to process q activations
            smaller priority number -> right of way
        """

        if options.get_opt('propagation') != "jitter_offset":
            raise options.argparse.ArgumentError("propagation must be set to \"jitter_offset\"")

        assert(q > 0)
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        logger.debug("w_spp_offset for " + task.name + " " + str(q) + " P:" + str(task.in_event_model.P) + " J:" + str(task.in_event_model.J))

        tasks_in_transaction, candidates = self.calculate_candidates(task)
        w = 0
        for candidate in candidates:
            w = max(w, self.w_spp_candidate(tasks_in_transaction, task, candidate, q - 1))
        logger.debug("window for %s is %f", task.name, w)
        assert(w >= q * task.wcet)

        return w


class SPPScheduler(analysis.Scheduler):
    """ Static-Priority-Preemptive Scheduler

    Priority is stored in task.scheduling_parameter,
    by default numerically lower numbers have a higher priority

    Policy for equal priority is FCFS (i.e. max. interference).
    """


    def __init__(self, priority_cmp=prio_low_wins_equal_fifo):
        analysis.Scheduler.__init__(self)

        # # priority ordering
        self.priority_cmp = priority_cmp

    def b_plus(self, task, q, details=None):
        """ This corresponds to Theorem 1 in [Lehoczky1990]_ or Equation 2.3 in [Richter2005]_. """
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        w = q * task.wcet

        while True:
            # logging.debug("w: %d", w)
            # logging.debug("e: %d", q * task.wcet)
            s = 0
            # logging.debug(task.name+" interferers "+ str([i.name for i in task.get_resource_interferers()]))
            for ti in task.get_resource_interferers():
                assert(ti.scheduling_parameter != None)
                assert(ti.resource == task.resource)
                if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter):  # equal priority also interferes (FCFS)
                    s += ti.wcet * ti.in_event_model.eta_plus(w)
                    # logging.debug("e: %s %d x %d", ti.name, ti.wcet, ti.in_event_model.eta_plus(w))

            w_new = q * task.wcet + s
            # print ("w_new: ", w_new)
            if w == w_new:
                assert(w >= q * task.wcet)
                if details is not None:
                    details['q*WCET'] = str(q) + '*' + str(task.wcet) + '=' + str(q * task.wcet)
                    for ti in task.get_resource_interferers():
                        if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter):
                            details[str(ti) + ':eta*WCET'] = str(ti.in_event_model.eta_plus(w)) + '*'\
                                + str(ti.wcet) + '=' + str(ti.wcet * ti.in_event_model.eta_plus(w))
                return w

            w = w_new


class SPPSchedulerRoundRobin(SPPScheduler):
    """ SPP scheduler with non-preemptive round-robin policy for equal priorities
    """

    def b_plus(self, task, q):
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        w = q * task.wcet
        while True:
            # logging.debug("w: %d", w)
            # logging.debug("e: %d", q * task.wcet)
            s = 0
            # logging.debug(task.name+" interferers "+ str([i.name for i in task.get_resource_interferers()]))
            for ti in task.get_resource_interferers():
                assert(ti.scheduling_parameter != None)
                assert(ti.resource == task.resource)
                if ti.scheduling_parameter == task.scheduling_parameter:  # equal priority -> round robin
                    # assume cooperative round-robin
                    s += ti.wcet * min(q, ti.in_event_model.eta_plus(w))
                elif self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter):  # lower priority number -> block
                    s += ti.wcet * ti.in_event_model.eta_plus(w)
                    # logging.debug("e: %s %d x %d", ti.name, ti.wcet, ti.in_event_model.eta_plus(w))


            w_new = q * task.wcet + s
            # print ("w_new: ", w_new)
            if w == w_new:
                break
            w = w_new

        assert(w >= q * task.wcet)
        return w


class TDMAScheduler(analysis.Scheduler):
    """ TDMA scheduler
        task.scheduling_parameter is the slot size of the respective task
    """

    def b_plus(self, task, q, details=None):
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        t_tdma = task.scheduling_parameter
        for tj in task.get_resource_interferers():
            t_tdma += tj.scheduling_parameter

        w = q * task.wcet + math.ceil(float(q * task.wcet) / task.scheduling_parameter) * (t_tdma - task.scheduling_parameter)

        assert(w >= q * task.wcet)

        if details is not None:
            details['q*WCET'] = str(q) + '*' + str(task.wcet) + '=' + str(q * task.wcet)
            for tj in task.get_resource_interferers():
                details["%s.TDMASlot" % (tj)] = str(tj.scheduling_parameter)
            details['I_TDMA'] = '%d*%d=%d' % (math.ceil(float(q * task.wcet) / task.scheduling_parameter),
                                      t_tdma - task.scheduling_parameter,
                                      math.ceil(float(q * task.wcet) / task.scheduling_parameter) * (t_tdma - task.scheduling_parameter))
        return w

