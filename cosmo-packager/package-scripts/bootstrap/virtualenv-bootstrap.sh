#!/usr/bin/env bash

function echop
{
	echo "${PKG_NAME}: $1"
}

function state_error
{
	echop "ERROR: ${1:-UNKNOWN} (status $?)" 1>&2
	exit 1
}

function check_pkg
{
	echop "checking to see if package $1 is installed..."
	dpkg -s $1 || state_error "package $1 is not installed"
	echop "package $1 is installed"
}

function check_user
{
	echop "checking to see if user $1 exists..."
	id -u $1 || state_error "user $1 doesn't exists"
	echop "user $1 exists"
}

function check_port
{
	echop "checking to see if port $1 is opened..."
	nc -z $1 $2 || state_error "port $2 is closed"
	echop "port $2 on $1 is opened"
}

function check_dir
{
	echop "checking to see if dir $1 exists..."
	if [ -d $1 ]; then
		echop "dir $1 exists"
	else
		state_error "dir $1 doesn't exist"
	fi
}

function check_file
{
	echop "checking to see if file $1 exists..."
	if [ -f $1 ]; then
		echop "file $1 exists"
		# if [ -$2 $1 ]; then
			# echop "$1 exists and contains the right attribs"
		# else
			# state_error "$1 exists but does not contain the right attribs"
		# fi
	else
		state_error "file $1 doesn't exists"
	fi
}

function check_upstart
{
	echop "checking to see if $1 daemon is running..."
	sudo status $1 || state_error "daemon $1 is not running"
	echop "daemon $1 is running"
}

function check_service
{
    echop "checking to see if $1 service is running..."
    sudo service $1 status || state_error "service $1 is not running"
    echop "service $1 is running"
}


PKG_NAME="virtualenv"
PKG_DIR="/packages/virtualenv"
BOOTSTRAP_LOG="/var/log/cloudify3-bootstrap.log"


echo "extracting ${PKG_NAME}..."
sudo tar -C ${PKG_DIR} -xvf ${PKG_DIR}/*.tar.gz
echo "removing tar..."
sudo rm ${PKG_DIR}/*.tar.gz
cd ${PKG_DIR}/virtualenv*
echo "installing ${PKG_NAME}..."
sudo python setup.py install
# sudo pip install --no-index --find-links="${PKG_DIR}" ${PKG_DIR}/*.tar.gz