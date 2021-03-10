#!/usr/bin/env python3

import rospy
from geometry_msgs.msg import PoseStamped
import numpy as np
import trj_interpolation as interpol

# radius of centauro wheels
R = 0.078


def roll_feet(freq):
    '''

    Args:
        freq: interpolation and publish frequency

    Returns:
        node for rolling the feet of centauro. Compatible with a driving stack.
    '''

    rospy.init_node('casannis_roller', anonymous=True)

    # map feet to a string for publishing to the corresponding topic
    id_name = ['FL', 'FR', 'HL', 'HR']

    f_init = []     # position of wheel frames
    f_cont = []     # position of contact frames

    # loop for all feet
    for i in range(len(id_name)):
        f_init.append(rospy.wait_for_message("/cartesian/" + id_name[i] + "_wheel/current_reference",
                                             PoseStamped,
                                             timeout=None))
        f_cont.append([f_init[i].pose.position.x, f_init[i].pose.position.y, f_init[i].pose.position.z - R])

    # contact points as array
    contacts = [np.array(x) for x in f_cont]

    # Get ROS Parameters

    # ID of the foot to be moved, get from parameters
    swing_id = rospy.get_param("~sw_id")    # from command line as swing_id:=1/2/3/4
    swing_id = swing_id.rstrip(']').lstrip('[').split(',')  # convert swing_id from "[a, b]" to [a,b]
    swing_id = [int(i) for i in swing_id]

    # number of rolling steps
    step_num = len(swing_id)

    # Target position of the foot wrt to the current position
    tgt_dx = rospy.get_param("~tgt_dx")  # get from command line as target_dx
    tgt_dy = rospy.get_param("~tgt_dy")
    tgt_dz = rospy.get_param("~tgt_dz")

    # variables to loop for swing legs
    swing_tgt = []  # target positions as list
    swing_t = []    # time periods of the swing phases
    f_pub_ = []     # list of publishers for the swing foot
    f_msg = []                  # list of messages to be published for swing feet
    swing_contacts = []         # contact positions of the swing feet
    interpl_trj = []    # interpolate the trj at a specified interpolation frequency

    for i in range(step_num):
        # targets
        swing_tgt.append([contacts[swing_id[i] - 1][0] + tgt_dx, contacts[swing_id[i] - 1][1] + tgt_dy, contacts[swing_id[i] - 1][2] + tgt_dz])

        # swing phases
        swing_t.append(rospy.get_param("~sw_t" + str(i+1)))  # from command line as swing_t:="[a,b]"
        swing_t[i] = swing_t[i].rstrip(']').lstrip('[').split(',')  # convert swing_t from "[a, b]" to [a,b]
        swing_t[i] = [float(i) for i in swing_t[i]]

        # swing feet trj publishers
        f_pub_.append(rospy.Publisher('/cartesian/' + id_name[swing_id[i] - 1] + '_wheel/reference',
                                      PoseStamped,
                                      queue_size=10))

        # feet trj messages
        f_msg.append(PoseStamped())

        # keep same orientation
        f_msg[i].pose.orientation = f_init[swing_id[i] - 1].pose.orientation

        swing_contacts.append(contacts[swing_id[i] - 1])

        interpl_trj.append(interpol.swing_trj_triangle(sw_curr=swing_contacts[i], sw_tgt=swing_tgt[i],
                                                       clear=0, sw_t=swing_t[i], total_t=[0.0, 12.0], resol=freq))

    # All points to be published
    N_total = int((swing_t[-1][1] - swing_t[0][0]) * freq)  # total points --> total time * interpolation frequency

    # approximate distance covered during swing
    tgt_ds = sum([interpl_trj[i]['s'] for i in range(step_num)])

    # mean velocity of the swing foot
    mean_foot_velocity = tgt_ds / step_num * (swing_t[0][1] - swing_t[0][0])
    print('Mean foot velocity is:', mean_foot_velocity, 'm/sec')

    rate = rospy.Rate(freq)  # Frequency trj publishing
    # loop interpolation points to publish on a specified frequency
    for counter in range(N_total):

        if not rospy.is_shutdown():

            for i in range(step_num):
                # swing foot
                f_msg[i].pose.position.x = interpl_trj[i]['x'][counter]
                f_msg[i].pose.position.y = interpl_trj[i]['y'][counter]
                # add radius as origin of the wheel frame is in the center
                f_msg[i].pose.position.z = interpl_trj[i]['z'][counter] + R

                # publish swing trajectory
                f_msg[i].header.stamp = rospy.Time.now()
                f_pub_[i].publish(f_msg[i])

        rate.sleep()


if __name__ == '__main__':

    # desired interpolation & publish frequency
    int_freq = 300

    try:
        roll_feet(int_freq)
    except rospy.ROSInterruptException:
        pass