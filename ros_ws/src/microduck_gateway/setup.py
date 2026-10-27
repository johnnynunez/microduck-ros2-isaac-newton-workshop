from setuptools import find_packages, setup
from glob import glob
setup(name='microduck_workshop_ros', version='0.1.0', packages=find_packages(),
      data_files=[('share/ament_index/resource_index/packages', ['resource/microduck_workshop_ros']),
                  ('share/microduck_workshop_ros', ['package.xml']),
                  ('share/microduck_workshop_ros/launch', glob('launch/*.launch.py'))],
      install_requires=['setuptools'], zip_safe=True,
      maintainer='Workshop maintainers', maintainer_email='johnny@nunez.dev',
      description='Simulation-only ROS 2 Lyrical gateway', license='Apache-2.0',
      entry_points={'console_scripts': ['gateway = microduck_gateway.node:main']})
